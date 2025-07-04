#!/usr/bin/env python3
############################################################################
#
# MODULE:    g.gui.rdigit
# AUTHOR(S): Anna Petrasova <kratochanna gmail.com>,
#            Tomas Zigo <tomas.zigo slovanet.sk> (standalone module)
# PURPOSE:   wxGUI Raster Digitizer
# COPYRIGHT: (C) 2014-2020 by Anna Petrasova, and the GRASS Development Team
#
#  This program is free software; you can redistribute it and/or
#  modify it under the terms of the GNU General Public License as
#  published by the Free Software Foundation; either version 2 of the
#  License, or (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful, but
#  WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
#  General Public License for more details.
#
############################################################################

# %module
# % description: Interactive editing and digitizing of raster maps.
# % keyword: general
# % keyword: GUI
# % keyword: raster
# % keyword: editing
# % keyword: digitizer
# %end
# %option G_OPT_R_OUTPUT
# % key: create
# % label: Name of new raster map to create
# % required: no
# % guisection: Create
# %end
# %option G_OPT_R_BASE
# % required: no
# % guisection: Create
# %end
# %option G_OPT_R_TYPE
# % answer: CELL
# % required: no
# % guisection: Create
# %end
# %option G_OPT_R_INPUT
# % key: edit
# % required: no
# % label: Name of existing raster map to edit
# % guisection: Edit
# %end
# %rules
# % exclusive: create, edit
# % required: create, edit
# % requires: base, create
# %end
from __future__ import annotations

import os

import grass.script as gs


def main():
    gs.set_raise_on_error(False)

    options, flags = gs.parser()

    # import wx only after running parser
    # to avoid issues with complex imports when only interface is needed
    import wx

    from grass.script.setup import set_gui_path

    set_gui_path()

    from core.render import Map
    from core.globalvar import ICONDIR
    from mapdisp.frame import MapPanel
    from gui_core.mapdisp import FrameMixin
    from mapdisp.main import DMonGrassInterface
    from core.settings import UserSettings

    # define classes which needs imports as local
    # for longer definitions, a separate file would be a better option
    class RDigitMapDisplay(FrameMixin, MapPanel):
        """Map display for wrapping map panel with r.digit methods and frame methods"""

        def __init__(
            self,
            parent,
            new_map=None,
            base_map=None,
            edit_map=None,
            map_type=None,
        ):
            MapPanel.__init__(
                self, parent=parent, Map=Map(), giface=DMonGrassInterface(None)
            )

            # set system icon
            parent.SetIcon(
                wx.Icon(os.path.join(ICONDIR, "grass.ico"), wx.BITMAP_TYPE_ICO)
            )

            # bindings
            parent.Bind(wx.EVT_CLOSE, self.OnCloseWindow)

            # extend shortcuts and create frame accelerator table
            self.shortcuts_table.append(
                (self.OnFullScreen, wx.ACCEL_NORMAL, wx.WXK_F11)
            )
            self._initShortcuts()

            # this giface issue not solved yet, we must set mapframe afterwards
            self._giface._mapframe = self
            self._giface.mapCreated.connect(self.OnMapCreated)
            self._mapObj = self.GetMap()

            # load raster map
            self._addLayer(name=new_map or edit_map)

            # switch toolbar
            self.AddToolbar("rdigit", fixed=True)

            rdigit = self.toolbars["rdigit"]
            if new_map:
                rdigit._mapSelectionCombo.Unbind(wx.EVT_COMBOBOX)
                self.rdigit.SelectNewMap(
                    standalone=True,
                    mapName=new_map,
                    bgMap=base_map,
                    mapType=map_type,
                )
                rdigit._mapSelectionCombo.Bind(
                    wx.EVT_COMBOBOX,
                    rdigit.OnMapSelection,
                )
            else:
                rdigit._mapSelectionCombo.SetSelection(n=1)
                rdigit.OnMapSelection()
            # use Close instead of QuitRDigit for standalone tool
            self.rdigit.quitDigitizer.disconnect(self.QuitRDigit)
            self.rdigit.quitDigitizer.connect(lambda: self.Close())

            # add Map Display panel to Map Display frame
            sizer = wx.BoxSizer(wx.VERTICAL)
            sizer.Add(self, proportion=1, flag=wx.EXPAND)
            parent.SetSizer(sizer)
            parent.Layout()

        def _addLayer(self, name, ltype="raster"):
            """Add layer into map

            :param str name: map name
            :param str ltype: layer type
            """
            self._mapObj.AddLayer(
                ltype=ltype,
                name=name,
                command=["d.rast", "map={}".format(name)],
                active=True,
                hidden=False,
                opacity=1.0,
                render=True,
            )

        def OnMapCreated(self, name, ltype, add: bool | None = None):
            """Add new created raster layer into map

            :param str name: map name
            :param str ltype: layer type
            :param bool add: unused
            """
            self._mapObj.Clean()
            self._addLayer(name=name, ltype=ltype)
            self.GetMapWindow().UpdateMap()

    kwargs = {
        "new_map": options["create"],
        "base_map": options["base"],
        "edit_map": options["edit"],
        "map_type": options["type"],
    }

    mapset = gs.gisenv()["MAPSET"]

    if kwargs["edit_map"]:
        edit_map = gs.find_file(
            name=kwargs["edit_map"],
            element="raster",
            mapset=mapset,
        )["fullname"]

        if not edit_map:
            gs.fatal(
                _("Raster map <{}> not found in current mapset.").format(
                    options["edit"],
                ),
            )
        else:
            kwargs["edit_map"] = edit_map
    elif kwargs["base_map"]:
        base_map = gs.find_file(
            name=kwargs["base_map"],
            element="raster",
            mapset=mapset,
        )["fullname"]
        if not base_map:
            gs.fatal(
                _("Base raster map <{}> not found in current mapset.").format(
                    options["base"],
                ),
            )
        kwargs["base_map"] = base_map

    # allow immediate rendering
    driver = UserSettings.Get(
        group="display",
        key="driver",
        subkey="type",
    )
    if driver == "png":
        os.environ["GRASS_RENDER_IMMEDIATE"] = "png"
    else:
        os.environ["GRASS_RENDER_IMMEDIATE"] = "cairo"

    app = wx.App()
    frame = wx.Frame(
        None,
        id=wx.ID_ANY,
        size=(850, 600),
        style=wx.DEFAULT_FRAME_STYLE,
        title=_("Raster Digitizer - GRASS GIS"),
    )
    frame = RDigitMapDisplay(parent=frame, **kwargs)
    frame.Show()

    app.MainLoop()


if __name__ == "__main__":
    main()
