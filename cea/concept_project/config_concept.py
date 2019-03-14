import os
import data.datalocator
import cea.config
import cea.inputlocator
import os

"""
=================
CEA
=================
"""
config = cea.config.Configuration()
assert os.path.exists(config.scenario), 'Scenario not found: %s' % config.scenario
locator_cea = cea.inputlocator.InputLocator(scenario=config.scenario)


"""
=================
Config Variables
=================
"""
LOCATOR = data.datalocator.get_data_path()

SCENARIO = '\\reference-case-WTP-reduced\\WTP_MIX_m\\'
# SCENARIO = '\\reference-case-WTP\\MIX_high_density\\'

if os.name == 'nt':  # Windows
    THREADS = 0
elif os.name == 'posix':  # Linux
    THREADS = 8
else:
    raise ValueError('No Linux or Windows OS!')


"""
=================
Global variables
=================
"""

# Economics data
INTEREST_RATE = 0.05  # 5% interest rate
ELECTRICITY_COST = 0.23  # SGD per kWh
THERMAL_COST = 0.12  # SGD per kWh

# Technical Data
V_BASE = 22.0  # in kV
S_BASE = 10.0  # in MVA
I_BASE = ((S_BASE/V_BASE) * (10**3))
APPROX_LOSS_HOURS = 3500