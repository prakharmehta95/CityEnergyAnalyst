from __future__ import division
import os
import pandas as pd
import py4design.py3dmodel.calculate as calculate
from py4design import py3dmodel
import py4design.py2radiance as py2radiance
import json
import shutil

from cea.utilities import epwreader

__author__ = "Jimeno A. Fonseca"
__copyright__ = "Copyright 2017, Architecture and Building Systems - ETH Zurich"
__credits__ = ["Jimeno A. Fonseca", "Kian Wee Chen"]
__license__ = "MIT"
__version__ = "0.1"
__maintainer__ = "Daren Thomas"
__email__ = "cea@arch.ethz.ch"
__status__ = "Production"


def create_sensor_input_file(rad, chunk_n):
    sensor_file_path = os.path.join(rad.data_folder_path, "points_"+str(chunk_n)+".pts")
    sensor_file = open(sensor_file_path, "w")
    sensor_pts_data = py2radiance.write_rad.sensor_file(rad.sensor_positions, rad.sensor_normals)
    sensor_file.write(sensor_pts_data)
    sensor_file.close()
    rad.sensor_file_path = sensor_file_path


def generate_sensor_surfaces(occface, wall_dim, roof_dim, srf_type, orientation, normal):
    mid_pt = py3dmodel.calculate.face_midpt(occface)
    location_pt = py3dmodel.modify.move_pt(mid_pt, normal, 0.01)
    moved_oface = py3dmodel.fetch.topo2topotype(py3dmodel.modify.move(mid_pt, location_pt, occface))
    if srf_type == 'roofs':
        xdim = ydim = roof_dim
    else:
        xdim = ydim = wall_dim
    # put it into occ and subdivide surfaces
    sensor_surfaces = py3dmodel.construct.grid_face(moved_oface, xdim, ydim)

    # calculate list of properties per surface
    sensor_dir = [normal for x in sensor_surfaces]
    sensor_cord = [py3dmodel.calculate.face_midpt(x) for x in sensor_surfaces]
    sensor_type = [srf_type for x in sensor_surfaces]
    sensor_orientation = [orientation for x in sensor_surfaces]
    sensor_area = [calculate.face_area(x)for x in sensor_surfaces]

    return sensor_dir, sensor_cord, sensor_type, sensor_area, sensor_orientation


def calc_sensors_building(building_geometry_dict, settings):
    sensor_dir_list = []
    sensor_cord_list = []
    sensor_type_list = []
    sensor_area_list = []
    sensor_orientation_list = []
    surfaces_types = ['walls', 'windows', 'roofs']
    sensor_vertical_grid_dim = settings.walls_grid
    sensor_horizontal_grid_dim = settings.roof_grid
    for srf_type in surfaces_types:
        occface_list = building_geometry_dict[srf_type]
        if srf_type == 'roofs':
            orientation_list = ['top']*len(occface_list)
            normals_list = [(0.0,0.0,1.0)] * len(occface_list)
        else:
            orientation_list = building_geometry_dict["orientation_"+srf_type]
            normals_list = building_geometry_dict["normals_"+srf_type]
        for orientation, normal, face in zip(orientation_list, normals_list, occface_list):
            sensor_dir, sensor_cord, sensor_type, sensor_area, sensor_orientation \
                = generate_sensor_surfaces(face, sensor_vertical_grid_dim, sensor_horizontal_grid_dim, srf_type, orientation, normal)
            sensor_dir_list.extend(sensor_dir)
            sensor_cord_list.extend(sensor_cord)
            sensor_type_list.extend(sensor_type)
            sensor_area_list.extend(sensor_area)
            sensor_orientation_list.extend(sensor_orientation)

    return sensor_dir_list, sensor_cord_list, sensor_type_list, sensor_area_list, sensor_orientation_list

def calc_sensors_zone(geometry_3D_zone, locator, settings):
    sensors_coords_zone = []
    sensors_dir_zone = []
    sensors_total_number_list = []
    names_zone = []
    sensors_code_zone = []
    for building_geometry in geometry_3D_zone:
        # building name
        building_name = building_geometry["name"]
        # get sensors in the building
        sensors_dir_building, sensors_coords_building, \
        sensors_type_building, sensors_area_building, sensor_orientation_building = calc_sensors_building(building_geometry, settings)

        # get the total number of sensors and store in lst
        sensors_number = len(sensors_coords_building)
        sensors_total_number_list.append(sensors_number)

        sensors_code = ['srf' + str(x) for x in range(sensors_number)]
        sensors_code_zone.append(sensors_code)

        # get the total list of coordinates and directions to send to daysim
        sensors_coords_zone.extend(sensors_coords_building)
        sensors_dir_zone.extend(sensors_dir_building)

        # get the name of all buildings
        names_zone.append(building_name)

        # save sensors geometry result to disk
        pd.DataFrame({'BUILDING':building_name,
                      'SURFACE': sensors_code,
                      'orientation':sensor_orientation_building,
                      'Xcoor': [x[0] for x in sensors_coords_building],
                      'Ycoor': [x[1] for x in sensors_coords_building],
                      'Zcoor': [x[2] for x in sensors_coords_building],
                      'Xdir': [x[0] for x in sensors_dir_building],
                      'Ydir':[x[1] for x in sensors_dir_building],
                      'Zdir':[x[2] for x in sensors_dir_building],
                      'AREA_m2': sensors_area_building,
                      'TYPE': sensors_type_building}).to_csv(locator.get_radiation_metadata(building_name), index=None)





    return sensors_coords_zone, sensors_dir_zone, sensors_total_number_list, names_zone, sensors_code_zone


def isolation_daysim(chunk_n, rad, geometry_3D_zone, locator, settings):
    weather_path = locator.get_weather_file()
    # folder for data work
    daysim_dir = locator.get_temporary_file("temp" + str(chunk_n))
    print('isolation_daysim: daysim_dir={daysim_dir}'.format(daysim_dir=daysim_dir))
    rad.initialise_daysim(daysim_dir, os.path.join(settings.daysim_bin_directory, ''))
    print("\tisolation_daysim: rad.hea_file: {}".format(rad.hea_file))
    print("\tisolation_daysim: rad.hea_filename: {}".format(rad.hea_filename))
    print("\tisolation_daysim: rad.daysimdir_ies: {}".format(rad.daysimdir_ies))
    print("\tisolation_daysim: rad.daysimdir_pts: {}".format(rad.daysimdir_pts))
    print("\tisolation_daysim: rad.daysimdir_rad: {}".format(rad.daysimdir_rad))
    print("\tisolation_daysim: rad.daysimdir_res: {}".format(rad.daysimdir_res))
    print("\tisolation_daysim: rad.daysimdir_tmp: {}".format(rad.daysimdir_tmp))
    print("\tisolation_daysim: rad.daysimdir_wea: {}".format(rad.daysimdir_wea))


    # calculate sensors
    print("Calculating and sending sensor points")
    sensors_coords_zone, sensors_dir_zone, sensors_number_zone, names_zone, \
    sensors_code_zone = calc_sensors_zone(geometry_3D_zone, locator, settings)
    rad.set_sensor_points(sensors_coords_zone, sensors_dir_zone)
    create_sensor_input_file(rad, chunk_n)
    print("\tisolation_daysim: rad.sensor_file_path: {}".format(rad.sensor_file_path))

    num_sensors = sum(sensors_number_zone)
    print("Starting Daysim simulation starts for buildings {buildings}".format(buildings=names_zone))
    print("Total number of sensors:  {num_sensors}".format(num_sensors=num_sensors))
    if num_sensors > 50000:
        raise ValueError('You are sending more than 50000 sensors at the same time, this '
                         'will eventually crash a daysim instance. To solve it, please reconfigure the radiation tool. '
                         'Just reduce the number of buildings per chunk and try again')

    # add_elevation_weather_file(weather_path)
    print('Executing epw2wea')
    rad.execute_epw2wea(weather_path, ground_reflectance = settings.albedo)
    print('Executing radfiles2daysim')
    rad.execute_radfiles2daysim()
    print('Writing radiance parameters')
    rad.write_radiance_parameters(settings.rad_ab, settings.rad_ad, settings.rad_as, settings.rad_ar, settings.rad_aa,
                                  settings.rad_lr, settings.rad_st, settings.rad_sj, settings.rad_lw, settings.rad_dj,
                                  settings.rad_ds, settings.rad_dr, settings.rad_dp)
    print('Executing gen_dc')
    rad.execute_gen_dc("w/m2")
    print('Executing ds_illum')
    rad.execute_ds_illum()
    print('Evaluating illumination per sensor')
    solar_res = rad.eval_ill_per_sensor()

    #erase daysim folder to avoid conflicts after every iteration
    print('Removing results folder')
    shutil.rmtree(daysim_dir)

    # check inconsistencies and replace by max value of weather file
    # check inconsistencies and replace by max value of weather file
    weatherfile = epwreader.epw_reader(weather_path)['glohorrad_Whm2'].values
    max_global = weatherfile.max()
    for i, value in enumerate(solar_res):
        solar_res[i] =  [0 if x > max_global else x for x in value]

    print("Writing results to disk")
    index = 0
    for building_name, sensors_number_building, sensor_code_building in zip(names_zone, sensors_number_zone, sensors_code_zone):
        selection_of_results = solar_res[index:index+sensors_number_building]
        items_sensor_name_and_result = dict(zip(sensor_code_building, selection_of_results))
        with open(locator.get_radiation_building(building_name), 'w') as outfile:
            json.dump(items_sensor_name_and_result, outfile)
        index = index + sensors_number_building

