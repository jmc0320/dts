# SPDX-License-Identifier: BSD-3-Clause
# Copyright(c) 2010-2014 Intel Corporation
#

import os
import shutil

from docutils.parsers.rst.directives import path

import framework.plotgraph as plotgraph
import framework.utils as utils

from .exception import VerifyFailure
from .plotgraph import Plot2DGraph
from .rst import path2Result

"""
Generate Plots for performance test results
"""


class tableData(object):
    def __init__(self):
        self.headers = []
        """
        Each data array corresponds to a column related to one of the headers above
        """
        self.data = []


class Plotting(object):

    path_2_result = path2Result
    plots_subfolder = "images"
    image_format = "png"

    default_bar_colours = [
        "#f70202",
        "#0f0b0b",
        "#123eed",
        "#07601b",
        "#36f760",
        "#87210d",
        "#512f28",
        "#11c6b1",
        "#45f94e",
        "#f94566",
    ]

    default_line_markers = ["o"]

    default_line_styles = ["--"]

    def __init__(self, crb, target, nic):

        # Ensure the folder exist
        try:

            path = "/".join(
                [Plotting.path_2_result, crb, target, nic, Plotting.plots_subfolder]
            )

            if not os.path.exists(path):
                os.makedirs(path)

            self.plots_path = path

        except Exception as e:
            raise VerifyFailure("Plot Error: " + str(e))

    def clear_all_plots(self, crb, target):
        shutil.rmtree(self.plots_path, True)

    def create_bars_plot(
        self,
        image_filename,
        plot_title,
        xdata,
        ydata,
        xlabel="",
        ylabel="",
        legend=[],
        bar_colours=default_bar_colours,
    ):

        for yseries in ydata:
            if len(xdata) != len(yseries):
                print(
                    utils.RED(
                        "The number of items in X axis (%s) and Y axis (%s) does not match."
                        % (xdata, ydata)
                    )
                )
                return ""

        image_path = "%s/%s.%s" % (
            self.plots_path,
            image_filename,
            Plotting.image_format,
        )

        pgraph = Plot2DGraph()
        pgraph.resetMe()

        # Set the number of bars, ydata contains a array per set of data
        pgraph.setNumPlots(len(ydata))
        pgraph.setNumSubplots(1)

        pgraph.setColors(bar_colours)
        pgraph.addBarYlabel(0, ylabel)
        pgraph.setBarLegends(0, legend)

        # For each value in the x axis add corresponding bar (array in ydata)
        for xvalue in range(len(xdata)):
            yvalues = [_[xvalue] for _ in ydata]
            pgraph.addBarData(0, xdata[xvalue], yvalues)

        # Dynamic adjustment of the bar widths for better plot appearance
        bar_width = 0.30 - 0.005 * ((len(xdata) * len(legend)) - 4)
        pgraph.setBarWidth(0, bar_width)

        pgraph.generateBar(plotName=image_path, title=plot_title)

        return image_path

    def create_lines_plot(
        self,
        image_filename,
        plot_title,
        xdata,
        ydata,
        xticks=[],
        yticks=[],
        xlabel="",
        ylabel="",
        legend=[],
        line_colours=default_bar_colours,
        line_markers=default_line_markers,
        line_styles=default_line_styles,
        addHline=False,
        hLine={},
        testing=False,
    ):

        image_path = "%s/%s.%s" % (
            self.plots_path,
            image_filename,
            Plotting.image_format,
        )

        pgraph = Plot2DGraph()
        pgraph.resetMe()

        numPlots = len(ydata) / len(xticks)
        numticks = len(xticks)

        # Set the number of bars, ydata contains a array per set of data
        pgraph.setNumPlots(numPlots)
        # TODO more than one plot per figure needs to be tested
        pgraph.setNumSubplots(1)

        # workaround
        if numPlots > len(line_colours):
            print("WARNING - numPlots > len(line_colours)")
            r = 0x00
            g = 0x66
            b = 0xFF
            for _ in range(numPlots - len(line_colours)):
                r = r % 256
                g = g % 256
                b = b % 256
                _ = "#%0.2x%0.2x%0.2x" % (r, g, b)
                line_colours.append(_)
                r += 7
                g -= 10
                b -= 9

        line_markers = line_markers * numPlots
        line_styles = line_styles * numPlots

        pgraph.setColors(line_colours)
        pgraph.setMarkers(line_markers)
        pgraph.setLineStyle(line_styles)

        pgraph.addBarYlabel(0, ylabel)
        pgraph.setBarLegends(0, legend)

        # For each value in the x axis add corresponding bar (array in ydata)
        for i in list(range(numPlots)):
            yDataStart = i * numticks
            pgraph.addPlotData(
                i,
                "Number of active pipes per output port",
                ylabel,
                xticks,
                [],
                xdata,
                ydata[yDataStart : (yDataStart + numticks)],
                [],
                [],
            )

        pgraph.xLen = 0.6
        pgraph.titleFontSize = 18
        pgraph.titleYOffset = 0.96
        pgraph.titleXOffset = 0.35

        if addHline:
            pgraph.horizontalLine = True
            pgraph.hLineName = hLine["name"]
            pgraph.hLine = hLine["value"]
            pgraph.hLineBoxX = hLine["boxXvalue"]
            pgraph.hLineBoxY = hLine["boxYvalue"]

        pgraph.generatePlot(
            plotName=image_path, keys=legend, title=plot_title, firstYvalue=1
        )

        return image_path
