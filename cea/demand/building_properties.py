# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import division

"""
Classes of building properties
"""

from __future__ import division

import numpy as np
import pandas as pd
from geopandas import GeoDataFrame as Gdf

from cea.demand import constants
from cea.utilities.dbf import dbf_to_dataframe

# import constants
H_F = constants.H_F
RSE = constants.RSE
H_MS = constants.H_MS
H_IS = constants.H_IS
B_F = constants.B_F
LAMBDA_AT = constants.LAMBDA_AT


class BuildingProperties(object):
    """
    Groups building properties used for the calc-thermal-loads functions. Stores the full DataFrame for each of the
    building properties and provides methods for indexing them by name.

    G. Happle   BuildingPropsThermalLoads   27.05.2016
    """

    def __init__(self, locator, override_variables=False):
        """
        Read building properties from input shape files and construct a new BuildingProperties object.

        :param locator: an InputLocator for locating the input files
        :type locator: cea.inputlocator.InputLocator

        :param override_variables: override_variables from config
        :type override_variables: bool

        :returns: BuildingProperties
        :rtype: BuildingProperties
        """

        print("read input files")
        prop_geometry = Gdf.from_file(locator.get_zone_geometry())
        prop_geometry['footprint'] = prop_geometry.area
        prop_geometry['perimeter'] = prop_geometry.length
        prop_geometry['Blength'], prop_geometry['Bwidth'] = self.calc_bounding_box_geom(locator.get_zone_geometry())
        prop_geometry = prop_geometry.drop('geometry', axis=1).set_index('Name')
        prop_hvac = dbf_to_dataframe(locator.get_building_hvac())
        prop_occupancy_df = dbf_to_dataframe(locator.get_building_occupancy()).set_index('Name')
        # Drop 'REFERENCE' column if it exists
        if 'REFERENCE' in prop_occupancy_df:
            prop_occupancy_df.drop('REFERENCE', 1, inplace=True)
        prop_occupancy_df.fillna(value=0.0, inplace=True)  # fix badly formatted occupancy file...
        prop_occupancy = prop_occupancy_df.loc[:, (prop_occupancy_df != 0).any(axis=0)]
        prop_architectures = dbf_to_dataframe(locator.get_building_architecture())
        prop_age = dbf_to_dataframe(locator.get_building_age()).set_index('Name')
        # Drop 'REFERENCE' column if it exists
        if 'REFERENCE' in prop_age:
            prop_age.drop('REFERENCE', 1, inplace=True)
        prop_comfort = dbf_to_dataframe(locator.get_building_comfort()).set_index('Name')
        prop_internal_loads = dbf_to_dataframe(locator.get_building_internal()).set_index('Name')
        prop_supply_systems_building = dbf_to_dataframe(locator.get_building_supply())

        # GET SYSTEMS EFFICIENCIES
        prop_supply_systems = get_properties_supply_sytems(locator, prop_supply_systems_building).set_index(
            'Name')

        # get temperatures of operation
        prop_HVAC_result = get_properties_technical_systems(locator, prop_hvac).set_index('Name')

        # get envelope properties
        prop_envelope = get_envelope_properties(locator, prop_architectures).set_index('Name')

        # apply overrides
        if override_variables:
            self._overrides = pd.read_csv(locator.get_building_overrides()).set_index('Name')
            prop_envelope = self.apply_overrides(prop_envelope)
            prop_internal_loads = self.apply_overrides(prop_internal_loads)
            prop_comfort = self.apply_overrides(prop_comfort)
            prop_HVAC_result = self.apply_overrides(prop_HVAC_result)

        # get properties of rc demand model
        prop_rc_model = self.calc_prop_rc_model(locator, prop_occupancy, prop_envelope,
                                                prop_geometry, prop_HVAC_result)

        # get solar properties
        solar = get_prop_solar(locator, prop_rc_model, prop_envelope).set_index('Name')

        # df_windows = geometry_reader.create_windows(surface_properties, prop_envelope)
        # TODO: to check if the Win_op and height of window is necessary.
        # TODO: maybe mergin branch i9 with CItyGML could help with this
        print("done")

        # save resulting data
        self._prop_supply_systems = prop_supply_systems
        self._prop_geometry = prop_geometry
        self._prop_envelope = prop_envelope
        self._prop_occupancy = prop_occupancy
        self._prop_HVAC_result = prop_HVAC_result
        self._prop_comfort = prop_comfort
        self._prop_internal_loads = prop_internal_loads
        self._prop_age = prop_age
        self._solar = solar
        self._prop_RC_model = prop_rc_model

    def calc_bounding_box_geom(self, geometry_shapefile):
        import shapefile
        sf = shapefile.Reader(geometry_shapefile)
        shapes = sf.shapes()
        len_shapes = len(shapes)
        bwidth = []
        blength = []
        for shape in range(len_shapes):
            bbox = shapes[shape].bbox
            coords_bbox = [coord for coord in bbox]
            delta1 = abs(coords_bbox[0] - coords_bbox[2])
            delta2 = abs(coords_bbox[1] - coords_bbox[3])
            if delta1 >= delta2:
                bwidth.append(delta2)
                blength.append(delta1)
            else:
                bwidth.append(delta1)
                blength.append(delta2)

        return blength, bwidth

    def apply_overrides(self, df):
        """Apply the overrides to `df`. This works by checking each column in the `self._overrides` dataframe
        and overwriting any columns in `df` with the same name.
        `self._overrides` and `df` are assumed to have the same index.
        """

        shared_columns = set(self._overrides.columns) & set(df.columns)
        for column in shared_columns:
            df[column] = self._overrides[column]
        return df

    def __len__(self):
        """return length of list_building_names"""
        return len(self.list_building_names())

    def list_building_names(self):
        """get list of all building names"""
        return self._prop_RC_model.index

    def list_uses(self):
        """get list of all uses (occupancy types)"""
        return list(self._prop_occupancy.columns)

    def get_prop_supply_systems(self, name_building):
        """get geometry of a building by name"""
        return self._prop_supply_systems.ix[name_building].to_dict()

    def get_prop_geometry(self, name_building):
        """get geometry of a building by name"""
        return self._prop_geometry.ix[name_building].to_dict()

    def get_prop_envelope(self, name_building):
        """get the architecture and thermal properties of a building by name"""
        return self._prop_envelope.ix[name_building].to_dict()

    def get_prop_occupancy(self, name_building):
        """get the occupancy properties of a building by name"""
        return self._prop_occupancy.ix[name_building].to_dict()

    def get_prop_hvac(self, name_building):
        """get HVAC properties of a building by name"""
        return self._prop_HVAC_result.ix[name_building].to_dict()

    def get_prop_rc_model(self, name_building):
        """get RC-model properties of a building by name"""
        return self._prop_RC_model.ix[name_building].to_dict()

    def get_prop_comfort(self, name_building):
        """get comfort properties of a building by name"""
        return self._prop_comfort.ix[name_building].to_dict()

    def get_prop_internal_loads(self, name_building):
        """get internal loads properties of a building by name"""
        return self._prop_internal_loads.ix[name_building].to_dict()

    def get_prop_age(self, name_building):
        """get age properties of a building by name"""
        return self._prop_age.ix[name_building].to_dict()

    def get_solar(self, name_building):
        """get solar properties of a building by name"""
        return self._solar.ix[name_building]

    def calc_prop_rc_model(self, locator, occupancy, envelope, geometry, hvac_temperatures):
        """
        Return the RC model properties for all buildings. The RC model used is described in ISO 13790:2008, Annex C (Full
        set of equations for simple hourly method).

        :param occupancy: The contents of the `occupancy.shp` file, indexed by building name. Each column is the name of an
            occupancy type (GYM, HOSPITAL, HOTEL, INDUSTRIAL, MULTI_RES, OFFICE, PARKING, etc.) except for the
            "PFloor" column which is a fraction of heated floor area.
            The occupancy types must add up to 1.0.
        :type occupancy: Gdf

        :param envelope: The contents of the `architecture.shp` file, indexed by building name.
            It contains the following fields:

            - n50: Air tightness at 50 Pa [h^-1].
            - type_shade: shading system type.
            - win_wall: window to wall ratio.
            - U_base: U value of the floor construction [W/m2K]
            - U_roof: U value of roof construction [W/m2K]
            - U_wall: U value of wall construction [W/m2K]
            - U_win: U value of window construction [W/m2K]
            - Hs: Fraction of gross floor area that is heated/cooled {0 <= Hs <= 1}
            - Cm_Af: Internal heat capacity per unit of area [J/K.m2]

        :type envelope: Gdf

        :param geometry: The contents of the `zone.shp` file indexed by building name - the list of buildings, their floor
            counts, heights etc.
            Includes additional fields "footprint" and "perimeter" as calculated in `read_building_properties`.
        :type geometry: Gdf

        :param hvac_temperatures: The return value of `get_properties_technical_systems`.
        :type hvac_temperatures: DataFrame

        :returns: RC model properties per building
        :rtype: DataFrame



        Sample result data calculated or manipulated by this method:

        Name: B153767

        datatype: float64

        =========    ============   ================================================================================================
        Column        e.g.          Description
        =========    ============   ================================================================================================
        Atot         4.564827e+03   (area of all surfaces facing the building zone in [m2])
        Aw           4.527014e+02   (area of windows in [m2])
        Am           6.947967e+03   (effective mass area in [m2])
        Aef          2.171240e+03   (floor area with electricity in [m2])
        Af           2.171240e+03   (conditioned floor area (heated/cooled) in [m2])
        Cm           6.513719e+08   (internal heat capacity in [J/k])
        Htr_is       1.574865e+04   (thermal transmission coefficient between air and surface nodes in RC-model in [W/K])
        Htr_em       5.829963e+02   (thermal transmission coefficient between exterior and thermal mass nodes in RC-model in [W/K])
        Htr_ms       6.322650e+04   (thermal transmission coefficient between surface and thermal mass nodes in RC-model in [W/K])
        Htr_op       5.776698e+02   (thermal transmission coefficient for opaque surfaces in [W/K])
        Hg           2.857637e+02   (steady-state thermal transmission coefficient to the ground in [W/K])
        HD           2.919060e+02   (direct thermal transmission coefficient to the external environment in [W/K])
        Htr_w        1.403374e+03   (thermal transmission coefficient for windows and glazing in [W/K])
        =========    ============   ================================================================================================

        FIXME: rename Awall_all to something more sane...
        """

        # calculate building geometry
        df = self.geometry_reader_radiation_daysim(locator, envelope, occupancy, geometry, H_F)
        df = df.merge(hvac_temperatures, left_index=True, right_index=True)

        for building in df.index.values:
            if hvac_temperatures.loc[building, 'type_hs'] == 'T0' and \
                    hvac_temperatures.loc[building, 'type_cs'] == 'T0' and df.loc[building, 'Hs'] > 0.0:
                df.loc[building, 'Hs'] = 0.0
                print('Building {building} has no heating and cooling system, Hs corrected to 0.'.format(
                    building=building))
        df['NFA_m2'] = df['GFA_m2'] * df['Ns']  # net floor area: all occupied areas in the building
        df['Af'] = df['GFA_m2'] * df['Hs']  # conditioned area: areas that are heated/cooled
        df['Aef'] = df['GFA_m2'] * df['Es']  # electrified area: share of gross floor area that is also electrified
        df['Atot'] = df['Af'] * LAMBDA_AT  # area of all surfaces facing the building zone

        if 'Cm_Af' in self.get_overrides_columns():
            # Internal heat capacity is not part of input, calculate [J/K]
            df['Cm'] = self._overrides['Cm_Af'] * df['Af']
        else:
            df['Cm'] = df['Cm_Af'] * df['Af']

        df['Am'] = df['Cm_Af'].apply(self.lookup_effective_mass_area_factor) * df['Af']  # Effective mass area in [m2]

        # Steady-state Thermal transmittance coefficients and Internal heat Capacity
        df['Htr_w'] = df['Aw'] * df['U_win']  # Thermal transmission coefficient for windows and glazing in [W/K]

        # direct thermal transmission coefficient to the external environment in [W/K]
        df['HD'] = df['Aop_sup'] * df['U_wall'] + df['footprint'] * df['U_roof']

        df['Hg'] = B_F * df['Aop_bel'] * df[
            'U_base']  # steady-state Thermal transmission coefficient to the ground. in W/K
        df['Htr_op'] = df['Hg'] + df['HD']
        df['Htr_ms'] = H_MS * df['Am']  # Coupling conductance 1 in W/K
        df['Htr_em'] = 1 / (1 / df['Htr_op'] - 1 / df['Htr_ms'])  # Coupling conductance 2 in W/K
        df['Htr_is'] = H_IS * df['Atot']

        fields = ['Atot', 'Aw', 'Am', 'Aef', 'Af', 'Cm', 'Htr_is', 'Htr_em', 'Htr_ms', 'Htr_op', 'Hg',  'HD', 'Aroof',
                  'U_wall', 'U_roof', 'U_win', 'U_base', 'Htr_w', 'GFA_m2', 'NFA_m2', 'surface_volume', 'Aop_sup',
                  'Aop_bel', 'footprint']
        result = df[fields]

        return result

    def geometry_reader_radiation_daysim(self, locator, envelope, occupancy, geometry, floor_height):
        """

        Reader which returns the radiation specific geometries from Daysim. Adjusts the imported data such that it is
        consistent with other imported geometry parameters.

        :param locator: an InputLocator for locating the input files

        :param envelope: The contents of the `architecture.shp` file, indexed by building name.

        :param occupancy: The contents of the `occupancy.shp` file, indexed by building name.

        :param geometry: The contents of the `zone.shp` file indexed by building name.

        :param floor_height: Height of the floor in [m].

        :return: Adjusted Daysim geometry data containing the following:

            - Name: Name of building.
            - Awall: Wall areas (length x height) multiplied by the FactorShade [m2]
            - Awall_all: Sum of wall areas for each building (including windows and voids) [m2]
            - Aw: Area of windows for each building (using mean window to wall ratio for building, excluding voids) [m2]
            - Aop_sup: Opaque wall areas above ground (excluding voids and windows) [m2]
            - Aop_bel: Opaque areas below ground (including ground floor, excluding voids and windows) [m2]
            - Aroof: Area of the roof (considered flat and equal to the building footprint) [m2]
            - GFA_m2: Gross floor area [m2]
            - floors: Sum of floors below ground (floors_bg) and floors above ground (floors_ag) [m2]
            - surface_volume: Surface to volume ratio [m^-1]

        :rtype: DataFrame

        Data is read from :py:meth:`cea.inputlocator.InputLocator.get_radiation_metadata`
        (e.g.
        ``C:/scenario/outputs/data/solar-radiation/{building_name}_geometry.csv``)

        Note: File generated by the radiation script. It contains the fields Name, Freeheight, FactorShade, height_ag and
        Shape_Leng. This data is used to calculate the wall and window areas.)

        """

        # add result columns to envelope df
        envelope['Awall'] = np.nan
        envelope['Awin'] = np.nan
        envelope['Aroof'] = np.nan

        # call all building geometry files in a loop
        for building_name in locator.get_zone_building_names():
            geometry_data = pd.read_csv(locator.get_radiation_metadata(building_name))
            geometry_data_sum = geometry_data.groupby(by='TYPE').sum()
            # do this in case the daysim radiation file did not included window
            if 'windows' in geometry_data.TYPE.values:
                if 'walls' in geometry_data.TYPE.values:
                    envelope.ix[building_name, 'Awall'] = geometry_data_sum.ix['walls', 'AREA_m2']
                    envelope.ix[building_name, 'Awin'] = geometry_data_sum.ix['windows', 'AREA_m2']
                    envelope.ix[building_name, 'Aroof'] = geometry_data_sum.ix['roofs', 'AREA_m2']
                else:
                    envelope.ix[building_name, 'Awall'] = 0.0 #when window to wall ration is 1, there are no walls.
                    envelope.ix[building_name, 'Awin'] = geometry_data_sum.ix['windows', 'AREA_m2']
                    envelope.ix[building_name, 'Aroof'] = geometry_data_sum.ix['roofs', 'AREA_m2']

            else:
                multiplier_win = 0.25 * (
                        envelope.ix[building_name, 'wwr_south'] + envelope.ix[building_name, 'wwr_east'] +
                        envelope.ix[building_name, 'wwr_north'] + envelope.ix[building_name, 'wwr_west'])
                envelope.ix[building_name, 'Awall'] = geometry_data_sum.ix['walls', 'AREA_m2'] * (1 - multiplier_win)
                envelope.ix[building_name, 'Awin'] = geometry_data_sum.ix['walls', 'AREA_m2'] * multiplier_win
                envelope.ix[building_name, 'Aroof'] = geometry_data_sum.ix['roofs', 'AREA_m2']

        df = envelope.merge(occupancy, left_index=True, right_index=True)

        # adjust envelope areas with PFloor
        df['Aw'] = df['Awin'] * (1 - df['void_deck'])
        # opaque areas (PFloor represents a factor according to the amount of floors heated)
        df['Aop_sup'] = df['Awall'] * (1 - df['void_deck'])
        # Areas below ground
        df = df.merge(geometry, left_index=True, right_index=True)
        df['floors'] = df['floors_bg'] + df['floors_ag']
        # opague areas in [m2] below ground including floor
        df['Aop_bel'] = df['height_bg'] * df['perimeter'] + df['footprint']
        df['GFA_m2'] = df['footprint'] * df['floors']  # gross floor area
        df['surface_volume'] = (df['Awin'] + df['Awall'] + df['Aroof']) / (df['GFA_m2'] * floor_height)  # surface to volume ratio

        return df

    def lookup_effective_mass_area_factor(self, cm):
        """
        Look up the factor to multiply the conditioned floor area by to get the effective mass area by building
        construction type.
        This is used for the calculation of the effective mass area "Am" in `get_prop_RC_model`.
        Standard values can be found in the Annex G of ISO EN13790

        :param: cm: The internal heat capacity per unit of area [J/m2].

        :return: Effective mass area factor (0, 2.5 or 3.2 depending on cm value).

        """

        if cm == 0.0:
            return 0.0
        elif 0.0 < cm <= 165000.0:
            return 2.5
        else:
            return 3.2

    def __getitem__(self, building_name):
        """return a (read-only) BuildingPropertiesRow for the building"""
        return BuildingPropertiesRow(name=building_name,
                                     geometry=self.get_prop_geometry(building_name),
                                     envelope=self.get_prop_envelope(building_name),
                                     occupancy=self.get_prop_occupancy(building_name),
                                     hvac=self.get_prop_hvac(building_name),
                                     rc_model=self.get_prop_rc_model(building_name),
                                     comfort=self.get_prop_comfort(building_name),
                                     internal_loads=self.get_prop_internal_loads(building_name),
                                     age=self.get_prop_age(building_name),
                                     solar=self.get_solar(building_name),
                                     supply=self.get_prop_supply_systems(building_name))

    def get_overrides_columns(self):
        """Return the list of column names in the `overrides.csv` file or an empty list if no such file
        is present."""

        if hasattr(self, '_overrides'):
            return list(self._overrides.columns)
        return []


class BuildingPropertiesRow(object):
    """Encapsulate the data of a single row in the DataSets of BuildingProperties. This class meant to be
    read-only."""


    def __init__(self, name, geometry, envelope, occupancy, hvac,
                 rc_model, comfort, internal_loads, age, solar, supply):
        """Create a new instance of BuildingPropertiesRow - meant to be called by BuildingProperties[building_name].
        Each of the arguments is a pandas Series object representing a row in the corresponding DataFrame."""

        self.name = name
        self.geometry = geometry
        self.architecture = EnvelopeProperties(envelope)
        self.occupancy = occupancy  # FIXME: rename to uses!
        self.hvac = hvac
        self.rc_model = rc_model
        self.comfort = comfort
        self.internal_loads = internal_loads
        self.age = age
        self.solar = SolarProperties(solar)
        self.supply = supply
        self.building_systems = self._get_properties_building_systems()

    def _get_properties_building_systems(self):

        """
        Method for defining the building system properties, specifically the nominal supply and return temperatures,
        equivalent pipe lengths and transmittance losses. The systems considered include an ahu (air
        handling unit, rsu(air recirculation unit), and scu/shu (sensible cooling / sensible heating unit).
        Note: it is assumed that building with less than a floor and less than 2 floors underground do not require
        heating and cooling, and are not considered when calculating the building system properties.

        :return: building_systems dict containing the following information:

            Pipe Lengths:

                - Lcww_dis: length of hot water piping in the distribution circuit (????) [m]
                - Lsww_dis: length of hot water piping in the distribution circuit (????) [m]
                - Lvww_dis: length of hot water piping in the distribution circuit (?????) [m]
                - Lvww_c: length of piping in the heating system circulation circuit (ventilated/recirc?) [m]
                - Lv: length vertical lines [m]

            Heating Supply Temperatures:

                - Ths_sup_ahu_0: heating supply temperature for AHU (C)
                - Ths_sup_aru_0: heating supply temperature for ARU (C)
                - Ths_sup_shu_0: heating supply temperature for SHU (C)

            Heating Return Temperatures:

                - Ths_re_ahu_0: heating return temperature for AHU (C)
                - Ths_re_aru_0: heating return temperature for ARU (C)
                - Ths_re_shu_0: heating return temperature for SHU (C)

            Cooling Supply Temperatures:

                - Tcs_sup_ahu_0: cooling supply temperature for AHU (C)
                - Tcs_sup_aru_0: cooling supply temperature for ARU (C)
                - Tcs_sup_scu_0: cooling supply temperature for SCU (C)

            Cooling Return Temperatures:

                - Tcs_re_ahu_0: cooling return temperature for AHU (C)
                - Tcs_re_aru_0: cooling return temperature for ARU (C)
                - Tcs_re_scu_0: cooling return temperature for SCU (C)

            Water supply temperature??:

                - Tww_sup_0: ?????

            Thermal losses in pipes:

                - Y: Linear trasmissivity coefficients of piping depending on year of construction [W/m.K]

            Form Factor Adjustment:

                - fforma: form factor comparison between real surface and rectangular ???

        :rtype: dict


        """

        # Refactored from CalcThermalLoads

        # gemoetry properties.

        Ll = self.geometry['Blength']
        Lw = self.geometry['Bwidth']
        nf_ag = self.geometry['floors_ag']
        nf_bg = self.geometry['floors_bg']
        phi_pipes = self._calculate_pipe_transmittance_values()

        # nominal temperatures
        Ths_sup_ahu_0 = float(self.hvac['Tshs0_ahu_C'])
        Ths_re_ahu_0 = float(Ths_sup_ahu_0 - self.hvac['dThs0_ahu_C'])
        Ths_sup_aru_0 = float(self.hvac['Tshs0_aru_C'])
        Ths_re_aru_0 = float(Ths_sup_aru_0 - self.hvac['dThs0_aru_C'])
        Ths_sup_shu_0 = float(self.hvac['Tshs0_shu_C'])
        Ths_re_shu_0 = float(Ths_sup_shu_0 - self.hvac['dThs0_shu_C'])
        Tcs_sup_ahu_0 = self.hvac['Tscs0_ahu_C']
        Tcs_re_ahu_0 = Tcs_sup_ahu_0 + self.hvac['dTcs0_ahu_C']
        Tcs_sup_aru_0 = self.hvac['Tscs0_aru_C']
        Tcs_re_aru_0 = Tcs_sup_aru_0 + self.hvac['dTcs0_aru_C']
        Tcs_sup_scu_0 = self.hvac['Tscs0_scu_C']
        Tcs_re_scu_0 = Tcs_sup_scu_0 + self.hvac['dTcs0_scu_C']

        Tww_sup_0 = self.hvac['Tsww0_C']
        # Identification of equivalent lenghts
        fforma = self._calc_form()  # factor form comparison real surface and rectangular
        Lv = (2 * Ll + 0.0325 * Ll * Lw + 6) * fforma  # length vertical lines
        if nf_ag < 2 and nf_bg < 2:  # it is assumed that building with less than a floor and less than 2 floors udnerground do not have
            Lcww_dis = 0
            Lvww_c = 0
        else:
            Lcww_dis = 2 * (Ll + 2.5 + nf_ag * H_F) * fforma  # length hot water piping circulation circuit
            Lvww_c = (2 * Ll + 0.0125 * Ll * Lw) * fforma  # length piping heating system circulation circuit

        Lsww_dis = 0.038 * Ll * Lw * nf_ag * H_F * fforma  # length hot water piping distribution circuit
        Lvww_dis = (Ll + 0.0625 * Ll * Lw) * fforma  # length piping heating system distribution circuit

        building_systems = pd.Series({'Lcww_dis': Lcww_dis,
                                      'Lsww_dis': Lsww_dis,
                                      'Lv': Lv,
                                      'Lvww_c': Lvww_c,
                                      'Lvww_dis': Lvww_dis,
                                      'Ths_sup_ahu_0': Ths_sup_ahu_0,
                                      'Ths_re_ahu_0': Ths_re_ahu_0,
                                      'Ths_sup_aru_0': Ths_sup_aru_0,
                                      'Ths_re_aru_0': Ths_re_aru_0,
                                      'Ths_sup_shu_0': Ths_sup_shu_0,
                                      'Ths_re_shu_0': Ths_re_shu_0,
                                      'Tcs_sup_ahu_0': Tcs_sup_ahu_0,
                                      'Tcs_re_ahu_0': Tcs_re_ahu_0,
                                      'Tcs_sup_aru_0': Tcs_sup_aru_0,
                                      'Tcs_re_aru_0': Tcs_re_aru_0,
                                      'Tcs_sup_scu_0': Tcs_sup_scu_0,
                                      'Tcs_re_scu_0': Tcs_re_scu_0,
                                      'Tww_sup_0': Tww_sup_0,
                                      'Y': phi_pipes,
                                      'fforma': fforma})
        return building_systems

    def _calculate_pipe_transmittance_values(self):
        """linear trasmissivity coefficients of piping W/(m.K)"""
        if self.age['built'] >= 1995 or self.age['HVAC'] > 1995:
            phi_pipes = [0.2, 0.3, 0.3]
        # elif 1985 <= self.age['built'] < 1995 and self.age['HVAC'] == 0:
        elif 1985 <= self.age['built'] < 1995:
            phi_pipes = [0.3, 0.4, 0.4]
            if self.age['HVAC'] == self.age['built']:
                print('Incorrect HVAC renovation year: if HVAC has not been renovated, the year should be set to 0')
        else:
            phi_pipes = [0.4, 0.4, 0.4]
        return phi_pipes

    def _calc_form(self):
        factor = self.geometry['footprint'] / (self.geometry['Bwidth'] * self.geometry['Blength'])
        return factor


class EnvelopeProperties(object):
    """Encapsulate a single row of the architecture input file for a building"""

    __slots__ = [u'a_roof', u'f_cros', u'n50', u'win_op', u'win_wall',
                 u'a_wall', u'rf_sh', u'e_wall', u'e_roof', u'G_win', u'e_win',
                 u'U_roof', u'Hs', u'Ns', u'Es', u'Cm_Af', u'U_wall', u'U_base', u'U_win']

    def __init__(self, envelope):
        self.a_roof = envelope['a_roof']
        self.n50 = envelope['n50']
        self.win_wall = envelope['wwr_south']
        self.a_wall = envelope['a_wall']
        self.rf_sh = envelope['rf_sh']
        self.e_wall = envelope['e_wall']
        self.e_roof = envelope['e_roof']
        self.G_win = envelope['G_win']
        self.e_win = envelope['e_win']
        self.U_roof = envelope['U_roof']
        self.Hs = envelope['Hs']
        self.Ns = envelope['Ns']
        self.Es = envelope['Es']
        self.Cm_Af = envelope['Cm_Af']
        self.U_wall = envelope['U_wall']
        self.U_base = envelope['U_base']
        self.U_win = envelope['U_win']


class SolarProperties(object):
    """Encapsulates the solar properties of a building"""

    __slots__ = ['I_sol']

    def __init__(self, solar):
        self.I_sol = solar['I_sol']


def get_properties_supply_sytems(locator, properties_supply):
    supply_heating = pd.read_excel(locator.get_life_cycle_inventory_supply_systems(), "HEATING")
    supply_cooling = pd.read_excel(locator.get_life_cycle_inventory_supply_systems(), "COOLING")
    supply_dhw = pd.read_excel(locator.get_life_cycle_inventory_supply_systems(), "DHW")
    supply_electricity = pd.read_excel(locator.get_life_cycle_inventory_supply_systems(), "ELECTRICITY")

    df_emission_heating = properties_supply.merge(supply_heating, left_on='type_hs', right_on='code')
    df_emission_cooling = properties_supply.merge(supply_cooling, left_on='type_cs', right_on='code')
    df_emission_dhw = properties_supply.merge(supply_dhw, left_on='type_dhw', right_on='code')
    df_emission_electricity = properties_supply.merge(supply_electricity, left_on='type_el', right_on='code')

    fields_emission_heating = ['Name', 'type_hs', 'type_cs', 'type_dhw', 'type_el',
                               'source_hs', 'scale_hs', 'eff_hs']
    fields_emission_cooling = ['Name', 'source_cs', 'scale_cs','eff_cs']
    fields_emission_dhw = ['Name', 'source_dhw', 'scale_dhw','eff_dhw']
    fields_emission_el = ['Name', 'source_el', 'scale_el','eff_el']

    result = df_emission_heating[fields_emission_heating].merge(df_emission_cooling[fields_emission_cooling],
                                                                on='Name').merge(
        df_emission_dhw[fields_emission_dhw], on='Name').merge(df_emission_electricity[fields_emission_el], on='Name')

    return result


def get_properties_technical_systems(locator, prop_HVAC):
    """
    Return temperature data per building based on the HVAC systems of the building. Uses the `emission_systems.xls`
    file to look up properties

    :param locator: an InputLocator for locating the input files
    :type locator: cea.inputlocator.InputLocator

    :param prop_HVAC: HVAC properties for each building (type of cooling system, control system, domestic hot water
                      system and heating system.
                      The values can be looked up in the contributors manual:
                      https://architecture-building-systems.gitbooks.io/cea-toolbox-for-arcgis-manual/content/building_properties.html#mechanical-systems
    :type prop_HVAC: geopandas.GeoDataFrame

    Sample data (first 5 rows)::

                     Name type_cs type_ctrl type_dhw type_hs type_vent
            0     B154862      T0        T1       T1      T1       T0
            1     B153604      T0        T1       T1      T1       T0
            2     B153831      T0        T1       T1      T1       T0
            3  B302022960      T0        T0       T0      T0       T0
            4  B302034063      T0        T0       T0      T0       T0

    :returns: A DataFrame containing temperature data for each building in the scenario. More information can be
              found in the contributors manual:
              https://architecture-building-systems.gitbooks.io/cea-toolbox-for-arcgis-manual/content/delivery_technologies.html
    :rtype: DataFrame

    Each row contains the following fields:

    ==========    =======   ===========================================================================
    Column           e.g.   Description
    ==========    =======   ===========================================================================
    Name          B154862   (building name)
    type_hs            T1   (copied from input, code for type of heating system)
    type_cs            T0   (copied from input, code for type of cooling system)
    type_dhw           T1   (copied from input, code for type of hot water system)
    type_ctrl          T1   (copied from input, code for type of controller for heating and cooling system)
    type_vent          T1   (copied from input, code for type of ventilation system)
    Tshs0_C            90   (heating system supply temperature at nominal conditions [C])
    dThs0_C            20   (delta of heating system temperature at nominal conditions [C])
    Qhsmax_Wm2        500   (maximum heating system power capacity per unit of gross built area [W/m2])
    dThs_C           0.15   (correction temperature of emission losses due to type of heating system [C])
    Tscs0_C             0   (cooling system supply temperature at nominal conditions [C])
    dTcs0_C             0   (delta of cooling system temperature at nominal conditions [C])
    Qcsmax_Wm2          0   (maximum cooling system power capacity per unit of gross built area [W/m2])
    dTcs_C            0.5   (correction temperature of emission losses due to type of cooling system [C])
    dT_Qhs            1.2   (correction temperature of emission losses due to control system of heating [C])
    dT_Qcs           -1.2   (correction temperature of emission losses due to control system of cooling[C])
    Tsww0_C            60   (dhw system supply temperature at nominal conditions [C])
    Qwwmax_Wm2        500   (maximum dwh system power capacity per unit of gross built area [W/m2])
    MECH_VENT        True   (copied from input, ventilation system configuration)
    WIN_VENT        False   (copied from input, ventilation system configuration)
    HEAT_REC         True   (copied from input, ventilation system configuration)
    NIGHT_FLSH       True   (copied from input, ventilation system control strategy)
    ECONOMIZER      False   (copied from input, ventilation system control strategy)
    ==========    =======   ===========================================================================

    Data is read from :py:meth:`cea.inputlocator.InputLocator.get_technical_emission_systems`
    (e.g.
    ``db/Systems/emission_systems.csv``)

    """

    prop_emission_heating = pd.read_excel(locator.get_technical_emission_systems(), 'heating')
    prop_emission_cooling = pd.read_excel(locator.get_technical_emission_systems(), 'cooling')
    prop_emission_dhw = pd.read_excel(locator.get_technical_emission_systems(), 'dhw')
    prop_emission_control_heating_and_cooling = pd.read_excel(locator.get_technical_emission_systems(), 'controller')
    prop_ventilation_system_and_control = pd.read_excel(locator.get_technical_emission_systems(), 'ventilation')

    df_emission_heating = prop_HVAC.merge(prop_emission_heating, left_on='type_hs', right_on='code')
    df_emission_cooling = prop_HVAC.merge(prop_emission_cooling, left_on='type_cs', right_on='code')
    df_emission_control_heating_and_cooling = prop_HVAC.merge(prop_emission_control_heating_and_cooling,
                                                              left_on='type_ctrl', right_on='code')
    df_emission_dhw = prop_HVAC.merge(prop_emission_dhw, left_on='type_dhw', right_on='code')
    df_ventilation_system_and_control = prop_HVAC.merge(prop_ventilation_system_and_control, left_on='type_vent',
                                                        right_on='code')

    fields_emission_heating = ['Name', 'type_hs', 'type_cs', 'type_dhw', 'type_ctrl', 'type_vent',
                               'Qhsmax_Wm2', 'dThs_C', 'Tshs0_ahu_C', 'dThs0_ahu_C', 'Th_sup_air_ahu_C', 'Tshs0_aru_C',
                               'dThs0_aru_C', 'Th_sup_air_aru_C', 'Tshs0_shu_C', 'dThs0_shu_C']
    fields_emission_cooling = ['Name', 'Qcsmax_Wm2', 'dTcs_C', 'Tscs0_ahu_C', 'dTcs0_ahu_C', 'Tc_sup_air_ahu_C',
                               'Tscs0_aru_C', 'dTcs0_aru_C', 'Tc_sup_air_aru_C', 'Tscs0_scu_C', 'dTcs0_scu_C']
    fields_emission_control_heating_and_cooling = ['Name', 'dT_Qhs', 'dT_Qcs']
    fields_emission_dhw = ['Name', 'Tsww0_C', 'Qwwmax_Wm2']
    fields_system_ctrl_vent = ['Name', 'MECH_VENT', 'WIN_VENT', 'HEAT_REC', 'NIGHT_FLSH', 'ECONOMIZER']

    result = df_emission_heating[fields_emission_heating].merge(df_emission_cooling[fields_emission_cooling],
                                                                on='Name').merge(
        df_emission_control_heating_and_cooling[fields_emission_control_heating_and_cooling],
        on='Name').merge(df_emission_dhw[fields_emission_dhw],
                         on='Name').merge(df_ventilation_system_and_control[fields_system_ctrl_vent], on='Name')

    # read region-specific control parameters (identical for all buildings), i.e. heating and cooling season
    prop_region_specific_control = pd.read_excel(locator.get_archetypes_system_controls(),
                                                 true_values=['True', 'TRUE', 'true'],
                                                 false_values=['False', 'FALSE', 'false', u'FALSE'],
                                                 dtype={'has-heating-season': bool,
                                                        'has-cooling-season': bool})  # read database

    result = result.join(pd.concat([prop_region_specific_control] * len(result), ignore_index=True))  # join on each row

    return result


def get_envelope_properties(locator, prop_architecture):
    """
    Gets the building envelope properties from
    ``databases/Systems/emission_systems.csv``, including the following:

    - prop_roof: Name, emissivity (e_roof), absorbtivity (a_roof), thermal resistance (U_roof), and fraction of
      heated space (Hs).
    - prop_wall: Name, emissivity (e_wall), absorbtivity (a_wall), thermal resistance (U_wall & U_base),
      window to wall ratio of north, east, south, west walls (wwr_north, wwr_east, wwr_south, wwr_west).
    - prop_win: Name, emissivity (e_win), solar factor (G_win), thermal resistance (U_win)
    - prop_shading: Name, shading factor (rf_sh).
    - prop_construction: Name, internal heat capacity (Cm_af), floor to ceiling voids (void_deck).
    - prop_leakage: Name, exfiltration (n50).

    Creates a merged df containing aforementioned envelope properties called envelope_prop.

    :return: envelope_prop
    :rtype: DataFrame

    """
    prop_roof = pd.read_excel(locator.get_envelope_systems(), 'ROOF')
    prop_wall = pd.read_excel(locator.get_envelope_systems(), 'WALL')
    prop_win = pd.read_excel(locator.get_envelope_systems(), 'WINDOW')
    prop_shading = pd.read_excel(locator.get_envelope_systems(), 'SHADING')
    prop_construction = pd.read_excel(locator.get_envelope_systems(), 'CONSTRUCTION')
    prop_leakage = pd.read_excel(locator.get_envelope_systems(), 'LEAKAGE')

    df_construction = prop_architecture.merge(prop_construction, left_on='type_cons', right_on='code')
    df_leakage = prop_architecture.merge(prop_leakage, left_on='type_leak', right_on='code')
    df_roof = prop_architecture.merge(prop_roof, left_on='type_roof', right_on='code')
    df_wall = prop_architecture.merge(prop_wall, left_on='type_wall', right_on='code')
    df_win = prop_architecture.merge(prop_win, left_on='type_win', right_on='code')
    df_shading = prop_architecture.merge(prop_shading, left_on='type_shade', right_on='code')

    fields_construction = ['Name', 'Cm_Af', 'void_deck', 'Hs', 'Ns', 'Es']
    fields_leakage = ['Name', 'n50']
    fields_roof = ['Name', 'e_roof', 'a_roof', 'U_roof']
    fields_wall = ['Name', 'wwr_north', 'wwr_west', 'wwr_east', 'wwr_south',
                   'e_wall', 'a_wall', 'U_wall', 'U_base']
    fields_win = ['Name', 'e_win', 'G_win', 'U_win', 'F_F']
    fields_shading = ['Name', 'rf_sh']

    envelope_prop = df_roof[fields_roof].merge(df_wall[fields_wall], on='Name').merge(df_win[fields_win],
                                                                                      on='Name').merge(
        df_shading[fields_shading], on='Name').merge(df_construction[fields_construction], on='Name').merge(
        df_leakage[fields_leakage], on='Name')

    return envelope_prop


def get_prop_solar(locator, prop_rc_model, prop_envelope):
    """
    Gets the sensible solar gains from calc_Isol_daysim and stores in a dataframe containing building 'Name' and
    I_sol (incident solar gains).

    :param locator: an InputLocator for locating the input files
    :param prop_rc_model: RC model properties of a building by name.
    :param prop_envelope: dataframe containing the building envelope properties.
    :return: dataframe containing the sensible solar gains for each building by name called result.
    :rtype: Dataframe
    """

    thermal_resistance_surface = RSE

    # create result data frame
    list_Isol = []

    # for every building
    for building_name in locator.get_zone_building_names():
        I_sol = calc_Isol_daysim(building_name, locator, prop_envelope, prop_rc_model, thermal_resistance_surface)
        list_Isol.append(I_sol)

    result = pd.DataFrame({'Name': list(locator.get_zone_building_names()), 'I_sol': list_Isol})

    return result


def calc_Isol_daysim(building_name, locator, prop_envelope, prop_rc_model, thermal_resistance_surface):
    """
    Reads Daysim geometry and radiation results and calculates the sensible solar heat loads based on the surface area
    and building envelope properties.

    :param building_name: Name of the building (e.g. B154862)
    :param locator: an InputLocator for locating the input files
    :param prop_envelope: contains the building envelope properties.
    :param prop_rc_model: RC model properties of a building by name.
    :param thermal_resistance_surface: Thermal resistance of building element.

    :return: I_sol: numpy array containing the sensible solar heat loads for roof, walls and windows.
    :rtype: np.array

    """

    # read daysim geometry
    geometry_data = pd.read_csv(locator.get_radiation_metadata(building_name)).set_index('SURFACE')
    geometry_data_roofs = geometry_data[geometry_data.TYPE == 'roofs']
    geometry_data_walls = geometry_data[geometry_data.TYPE == 'walls']

    # do this in case the daysim radiation file did not included window
    if 'windows' in geometry_data.TYPE.values:
        geometry_data_windows = geometry_data[geometry_data.TYPE == 'windows']
        multiplier_wall = 1
        multiplier_win = 1
    else:
        geometry_data_windows = geometry_data[geometry_data.TYPE == 'walls']
        multiplier_win = 0.25 * (
                prop_envelope.ix[building_name, 'wwr_south'] + prop_envelope.ix[building_name, 'wwr_east'] +
                prop_envelope.ix[
                    building_name, 'wwr_north'] + prop_envelope.ix[building_name, 'wwr_west'])
        multiplier_wall = 1 - multiplier_win

    # read daysim radiation
    radiation_data = pd.read_json(locator.get_radiation_building(building_name))
    # sum wall
    # solar incident on all walls [W]
    I_sol_wall = np.array(
        [geometry_data_walls.ix[surface, 'AREA_m2'] * multiplier_wall * radiation_data[surface] for surface in
         geometry_data_walls.index]).sum(axis=0)
    # sensible gain on all walls [W]
    I_sol_wall = I_sol_wall * prop_envelope.ix[building_name, 'a_wall'] * thermal_resistance_surface * \
                 prop_rc_model.ix[building_name, 'U_wall']
    # sum roof

    # solar incident on all roofs [W]
    I_sol_roof = np.array([geometry_data_roofs.ix[surface, 'AREA_m2'] * radiation_data[surface] for surface in
                           geometry_data_roofs.index]).sum(axis=0)
    # sensible gain on all roofs [W]
    I_sol_roof = I_sol_roof * prop_envelope.ix[building_name, 'a_roof'] * thermal_resistance_surface * \
                 prop_rc_model.ix[building_name, 'U_roof']
    # sum window, considering shading
    from cea.technologies import blinds
    Fsh_win = [np.vectorize(blinds.calc_blinds_activation)(radiation_data[surface],
                                                           prop_envelope.ix[building_name, 'G_win'],
                                                           prop_envelope.ix[building_name, 'rf_sh']) for surface
               in geometry_data_windows.index]

    I_sol_win = [geometry_data_windows.ix[surface, 'AREA_m2'] * multiplier_win * radiation_data[surface]
                 for surface in geometry_data_windows.index]

    I_sol_win = np.array([x * y * (1 - prop_envelope.ix[building_name, 'F_F']) for x, y in zip(I_sol_win, Fsh_win)]).sum(axis=0)

    # sum
    I_sol = I_sol_wall + I_sol_roof + I_sol_win

    return I_sol


def calc_Isol_arcgis(I_sol_average, prop_rc_model, prop_envelope, thermal_resistance_surface):
    """
    This function calculates the effective collecting solar area accounting for use of blinds according to ISO 13790,
    for the sake of simplicity and to avoid iterations, the delta is calculated based on the last time step.

    :param t: time of the year
    :param bpr: building properties object
    :return: I_sol: numpy array containing the sensible solar heat loads for roof, walls and windows.
    :rtype: np.array

    """
    from cea.technologies import blinds
    Fsh_win = np.vectorize(blinds.calc_blinds_activation)(I_sol_average, prop_envelope.G_win, prop_envelope.rf_sh)

    Asol_wall = prop_rc_model['Aop_sup'] * prop_envelope.a_wall * thermal_resistance_surface * prop_rc_model['U_wall']
    Asol_roof = prop_rc_model['Aroof'] * prop_envelope.a_roof * thermal_resistance_surface * prop_rc_model['U_roof']
    Asol_win = Fsh_win * prop_rc_model['Aw'] * (1 - prop_envelope.F_F)

    I_sol = I_sol_average * (Asol_wall + Asol_roof + Asol_win)

    return I_sol
