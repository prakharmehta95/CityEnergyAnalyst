from __future__ import division
from __future__ import print_function

import numpy as np
from plotly.offline import plot
import plotly.graph_objs as go
from cea.plots.variable_naming import LOGO
from cea.plots.color_code import ColorCodeCEA
COLOR = ColorCodeCEA()


def supply_return_ambient_temp_plot(data_frame, data_frame_2, analysis_fields, title, output_path, axis_title):

    traces = []
    for field in analysis_fields:
        y = data_frame[field].values
        #sort by ambient temperature
        y = np.vstack((np.array(data_frame_2.values.T), y))
        y[0,:] = y[0,:][y[0,:].argsort()]
        y[1, :] = y[1, :][y[0, :].argsort()]
        trace = go.Scatter(x=y[0], y=y[1], name=field.split('_', 1)[0],
                               marker=dict(color=COLOR.get_color_rgb(field.split('_', 1)[0])))
        traces.append(trace)

    # CREATE FIRST PAGE WITH TIMESERIES
    layout = dict(images=LOGO, title=title, yaxis=dict(title=axis_title), xaxis=dict(title='Ambient Temperature [deg C]'))

    fig = dict(data=traces, layout=layout)
    plot(fig,  auto_open=False, filename=output_path)

    return {'data': traces, 'layout': layout}