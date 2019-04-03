from __future__ import division
import numpy as np
import pandas as pd
import os
from cea.utilities.physics import calc_rho_air
from cea.plots.demand.comfort_chart import p_w_from_rh_p_and_ws, p_ws_from_t, hum_ratio_from_p_w_and_p

# BUILDINGS_DEMANDS_COLUMNS = ['Name', 'Qww_sys_kWh', 'Qcdata_sys_kWh',
#                              'Qcs_sen_ahu_kWh', 'Qcs_sen_aru_kWh', 'Qcs_sen_scu_kWh', 'Qcs_sen_sys_kWh',
#                              'Qcs_lat_ahu_kWh', 'Qcs_lat_aru_kWh', 'Qcs_lat_sys_kWh',
#                              'Qcs_sys_ahu_kWh', 'Qcs_sys_aru_kWh', 'Qcs_sys_scu_kWh',
#                              'people', 'x_int', 'T_int_C', 'T_ext_C']

TSD_COLUMNS = ['T_ext', 'rh_ext', 'w_int', 'people', 'I_sol_and_I_rad', 'Q_gain_lat_peop', 'Q_gain_sen_peop',
               'Q_gain_sen_vent',
               'g_dhu_ld', 'm_ve_inf', 'm_ve_mech', 'm_ve_rec', 'm_ve_required', 'm_ve_window']

Q_GAIN_ENV = ['Q_gain_sen_base', 'Q_gain_sen_roof', 'Q_gain_sen_wall', 'Q_gain_sen_wind']

# 'Q_loss_sen_base','Q_loss_sen_roof', 'Q_loss_sen_wall', 'Q_loss_sen_wind']

Q_GAIN_INT = ['Q_gain_sen_app', 'Q_gain_sen_data', 'Q_gain_sen_light', 'Q_gain_sen_pro', 'Q_loss_sen_ref']

TSD_COLUMNS.extend(Q_GAIN_ENV)
TSD_COLUMNS.extend(Q_GAIN_INT)

H_WE_Jperkg = 2466e3  # (J/kg) Latent heat of vaporization of water [section 6.3.6 in ISO 52016-1:2007]
floor_height_m = 2.5  # FIXME: read from CEA
v_CO2_Lpers = 0.0048  # [L/s/person]
rho_CO2_kgperm3 = 1.98  # [kg/m3]
CO2_env_ppm = 400 / 1e6  # [m3 CO2/m3]
CO2_int_max_ppm = 800 / 1e6  # [m3 CO2/m3]


def main():
    building_names = ['B001']
    Ve_lps = {'B001': 18.24, 'B002': 15.6, 'B007': 13.53}
    Af_m2 = {'B001': 28495.062, 'B002': 28036.581, 'B007': 30743.113}
    SS553_lps_m2 = 0.6

    for name in building_names:
        # read demand output
        # demand_df = pd.read_csv(path_to_demand_output(name)['csv'], usecols=(BUILDINGS_DEMANDS_COLUMNS))
        tsd_df = pd.read_excel(path_to_demand_output(name)['xls'], usecols=(TSD_COLUMNS))

        # reduce to 24 hours
        start_t = 3217
        end_t = (start_t + 24)
        # reduced_demand_df = demand_df[start_t:end_t]
        reduced_tsd_df = tsd_df[start_t:end_t]
        # output_df = pd.concat([demand_df[start_t:end_t], tsd_df[start_t:end_t]], axis=1)
        output_df = pd.DataFrame()

        # change units
        output_df['rh_ext'] = reduced_tsd_df['rh_ext'] / 100
        output_df['w_ext'] = np.vectorize(calc_w_from_rh)(output_df['rh_ext'], reduced_tsd_df['T_ext'])

        ## building size
        output_df.loc[:, 'Af_m2'] = Af_m2[name]
        output_df.loc[:, 'Vf_m3'] = floor_height_m * Af_m2[name]

        ## humidity gain
        output_df['w_gain_occ_kgpers'] = reduced_tsd_df['w_int']
        output_df['w_gain_infil_kgpers'] = reduced_tsd_df['m_ve_inf'] * output_df['w_ext'] / 1000

        ## heat gain
        calc_sensible_gains(output_df, reduced_tsd_df)
        # output_df['Q_gain_kWh'] = abs(reduced_demand_df['Qcs_sen_sys_kWh'])  # redundant

        ## CO2 gain
        calc_CO2_gains(output_df, reduced_tsd_df)

        # add hour of the day
        output_df['hour'] = range(1, 25)
        output_df = output_df.round(4)
        # output_df.ix[1:].to_csv(path_to_osmose_project(name),index=False)

        # save to xls
        writer = pd.ExcelWriter(path_to_ampl_project(name), index=False)
        output_df.to_excel(writer, 'Building', index=False)
        writer.save()
    return


def calc_CO2_gains(output_df, reduced_tsd_df):
    output_df['CO2_ext_ppm'] = CO2_env_ppm  # TODO: get acutal profile?
    output_df['CO2_max_ppm'] = CO2_int_max_ppm
    # from occupants
    reduced_tsd_df['v_CO2_occupant_m3pers'] = calc_co2_from_occupants(reduced_tsd_df['people'])
    # output_df['v_CO2_occupant_m3perhr'] = calc_co2_from_occupants(demand_df['people'])*3600  #to hr
    # from inlet air
    reduced_tsd_df['rho_air'] = np.vectorize(calc_rho_air)(reduced_tsd_df['T_ext'])
    reduced_tsd_df['v_in_infil_window'] = (reduced_tsd_df['m_ve_inf'] + reduced_tsd_df['m_ve_window']) / \
                                          reduced_tsd_df['rho_air']
    reduced_tsd_df['v_CO2_infil_window_m3pers'] = reduced_tsd_df['v_in_infil_window'] * output_df['CO2_ext_ppm']
    output_df['v_CO2_in_infil_occupant_m3pers'] = reduced_tsd_df['v_CO2_occupant_m3pers'] + reduced_tsd_df[
        'v_CO2_infil_window_m3pers']
    # output_df['m_exhaust_from_CO2'] = np.vectorize(calc_m_exhaust_from_CO2)(output_df['CO2_max_ppm'],
    #                                                                         output_df['CO2_ext_ppm'],
    #                                                                         reduced_tsd_df['v_CO2_occupant_m3pers'],
    #                                                                         reduced_tsd_df['rho_air'])


def calc_sensible_gains(output_df, reduced_tsd_df):
    # radiation
    reduced_tsd_df['Q_gain_rad_kWh'] = reduced_tsd_df['I_sol_and_I_rad'] / 1000
    # environment
    reduced_tsd_df['Q_gain_env_kWh'] = reduced_tsd_df.loc[:, Q_GAIN_ENV].sum(axis=1) / 1000
    # internal (appliances, lighting...)
    reduced_tsd_df['Q_gain_int_kWh'] = reduced_tsd_df.loc[:, Q_GAIN_INT].sum(axis=1) / 1000
    # occupant
    reduced_tsd_df['Q_gain_occ_kWh'] = reduced_tsd_df['Q_gain_sen_peop'] / 1000
    # total
    output_df['Q_gain_total_kWh'] = reduced_tsd_df['Q_gain_rad_kWh'] + reduced_tsd_df['Q_gain_env_kWh'] + reduced_tsd_df[
        'Q_gain_int_kWh'] + reduced_tsd_df['Q_gain_occ_kWh']


def calc_co2_from_occupants(occupants):
    # from Jeremie's thesis
    v_CO2_m3pers = v_CO2_Lpers / 1000
    v_CO2_m3pers = v_CO2_m3pers * occupants
    return v_CO2_m3pers


def calc_w_from_rh(rh, t):
    pws = p_ws_from_t(t)
    pw = p_w_from_rh_p_and_ws(rh, pws)
    p = 101325  # [Pa]
    w = hum_ratio_from_p_w_and_p(pw, p)
    return w * 1000  # g/kg d.a.


def calc_m_exhaust_from_CO2(CO2_room, CO2_ext, CO2_gain_m3pers, rho_air):
    # assuming m_exhaust = m_ve_mech
    m_exhaust_kgpers = CO2_gain_m3pers * rho_air / (CO2_room - CO2_ext)
    return m_exhaust_kgpers


def path_to_demand_output(building_name):
    case = 'WTP_CBD_m'
    path_to_file = {}
    path_to_folder = 'C:\\CEA_cases\\%s\\outputs\\data\\demand' % case
    path_to_file['csv'] = os.path.join(path_to_folder, '%s.%s' % (building_name, 'csv'))
    path_to_file['xls'] = os.path.join(path_to_folder, '%s.%s' % (building_name, 'xls'))
    return path_to_file


def path_to_osmose_project(building_name):
    format = 'csv'
    path_to_folder = 'C:\\Users\\Shanshan\\Documents\\GitHub\\ampl'
    path_to_file = os.path.join(path_to_folder, '%s_from_cea.%s' % (building_name, format))
    return path_to_file


def path_to_ampl_project(building_name):
    format = 'xls'
    path_to_folder = 'C:\\Users\\Shanshan\\Documents\\GitHub\\ampl'
    path_to_file = os.path.join(path_to_folder, '%s_from_cea.%s' % (building_name, format))
    return path_to_file


if __name__ == '__main__':
    main()