bl_info = {
    "name": "ToPu_Time Scale Display",
    "author": "http4211",
    "version": (1, 0, 0),
    "blender": (4, 0, 0),
    "location": "Timeline / Viewport",
    'tracker_url': 'https://github.com/http4211/ToPu_Time-Scale-Display',
    "description": "Displays seconds in Timeline and 3D Viewport with customizable overlays.",
    "category": "Interface",
}

import bpy
import importlib

from . import viewport_seconds_display
from . import timeline_seconds_display

importlib.reload(viewport_seconds_display)
importlib.reload(timeline_seconds_display)

# アドオンの設定クラス
class ToPuAddonPreferences(bpy.types.AddonPreferences):
    bl_idname = __name__

    enable_viewport: bpy.props.BoolProperty(
        name="Enable Viewport Display",
        default=True,
        update=lambda self, ctx: update_modules()
    )
    enable_timeline: bpy.props.BoolProperty(
        name="Enable Timeline Display",
        default=True,
        update=lambda self, ctx: update_modules()
    )

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "enable_viewport")
        layout.prop(self, "enable_timeline")

# モジュール状態フラグ
_is_viewport_enabled = False
_is_timeline_enabled = False

def update_modules():
    prefs = bpy.context.preferences.addons.get(__name__)
    if not prefs:
        return
    prefs = prefs.preferences
    global _is_viewport_enabled, _is_timeline_enabled

    if prefs.enable_viewport and not _is_viewport_enabled:
        viewport_seconds_display.register()
        _is_viewport_enabled = True
    elif not prefs.enable_viewport and _is_viewport_enabled:
        viewport_seconds_display.unregister()
        _is_viewport_enabled = False

    if prefs.enable_timeline and not _is_timeline_enabled:
        timeline_seconds_display.register()
        _is_timeline_enabled = True
    elif not prefs.enable_timeline and _is_timeline_enabled:
        timeline_seconds_display.unregister()
        _is_timeline_enabled = False

def register():
    bpy.utils.register_class(ToPuAddonPreferences)
    update_modules()

def unregister():
    global _is_viewport_enabled, _is_timeline_enabled
    if _is_viewport_enabled:
        viewport_seconds_display.unregister()
        _is_viewport_enabled = False
    if _is_timeline_enabled:
        timeline_seconds_display.unregister()
        _is_timeline_enabled = False
    bpy.utils.unregister_class(ToPuAddonPreferences)
