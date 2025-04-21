bl_info = {
    "name": "ToPu_Timeline Seconds Display",
    "author": "http4211",
    "version": (1, 0),
    "blender": (4, 0, 0),
    "location": "Timeline / Graph / Drivers / NLA / DopeSheet",
    "description": "Timeline seconds with adjustable subdivisions, per area mode (top/bottom), auto-save, and popup-only UI.",
    "category": "Animation",
}

import bpy
import sys
import math
import gpu
import blf
import os
import json
from gpu_extras.batch import batch_for_shader

shader = gpu.shader.from_builtin('UNIFORM_COLOR')
handle_map = {}
addon_dir = os.path.dirname(__file__)
default_preset_path = os.path.join(addon_dir, "timeline_preset.json")

def auto_save_preset(self, context):
    save_preset(default_preset_path)
class TickSubSettings(bpy.types.PropertyGroup):
    enabled: bpy.props.BoolProperty(name="EnableDisplay", default=True, update=auto_save_preset)
    base_offset: bpy.props.IntProperty(name="Vertical Offset", default=23, min=-200, max=200, update=auto_save_preset)
    tick_scale: bpy.props.FloatProperty(name="Scale Size", default=1.0, min=0.1, max=10.0, update=auto_save_preset)
    main_tick_height: bpy.props.FloatProperty(name="Main scale height", default=13.0, min=1.0, max=100.0, update=auto_save_preset)
    sub_tick_height: bpy.props.FloatProperty(name="Sub scale height", default=15.0, min=1.0, max=100.0, update=auto_save_preset)
    label_offset: bpy.props.IntProperty(name="Number Offset", default=15, min=-100, max=100, update=auto_save_preset)
    label_size: bpy.props.IntProperty(name="Number Size", default=11, min=0, max=72, update=auto_save_preset)
    color_main: bpy.props.FloatVectorProperty(name="Main scale Color", subtype='COLOR', size=4, default=(1, 0.5, 0.0, 0.75), min=0.0, max=1.0, update=auto_save_preset)
    color_sub: bpy.props.FloatVectorProperty(name="Sub scale Color", subtype='COLOR', size=4, default=(0.9, 0.9, 0.9, 0.5), min=0.0, max=1.0, update=auto_save_preset)
    color_text: bpy.props.FloatVectorProperty(name="Number Color", subtype='COLOR', size=4, default=(1, 0.95, 1, 0.55), min=0.0, max=1.0, update=auto_save_preset)
    subdivisions: bpy.props.IntProperty(name="Sub scale partitions", default=4, min=0, max=20, update=auto_save_preset)
# --- 🆕 ここから追加 ---
class BaseframeSettings(bpy.types.PropertyGroup):
    def update_use_baseframe_offset(self, context):
        if self.use_baseframe_offset:
            master = context.scene.timeline_tick_settings_master
            master.offset_start_frame_enabled = False

    use_baseframe_offset: bpy.props.BoolProperty(
        name="Use base frame offset",
        description="Offset the start frame",
        default=False,
        update=update_use_baseframe_offset
    )
    
    baseframe_offset_value: bpy.props.IntProperty(
        name="Base frame offset value",
        description="Number of frames to offset",
        default=0
    )


def update_offset_start_frame_enabled(self, context):
    if self.offset_start_frame_enabled:
        baseframe = context.scene.baseframe_settings
        baseframe.use_baseframe_offset = False

# 全体設定：今まで通り（裏方用）
class TickMasterSettings(bpy.types.PropertyGroup):
    mode: bpy.props.EnumProperty(
        name="Display position",
        items=[('BOTTOM', "BOTTOM", ""), ('TOP', "TOP", "")],
        default='TOP',
        update=auto_save_preset
    )
    offset_start_frame_enabled: bpy.props.BoolProperty(
        name="Use rendering range",
        default=False,
        update=update_offset_start_frame_enabled
    )
    top: bpy.props.PointerProperty(type=TickSubSettings)
    bottom: bpy.props.PointerProperty(type=TickSubSettings)

# ★ここにエリアごとの「モード（上/下）」を追加！！
class TimelineSecondsAreaSettings(bpy.types.PropertyGroup):
    enabled: bpy.props.BoolProperty(name="Enable seconds display", default=True)
    mode: bpy.props.EnumProperty(
        name="Display position",
        items=[('BOTTOM', "BOTTOM", ""), ('TOP', "TOP", "")],
        default='TOP'
    )
def get_area_key(area: bpy.types.Area) -> str:
    base_key = str(area.as_pointer())
    if area.spaces:
        space = area.spaces.active
        base_key += f"##space:{space.as_pointer()}"
        if area.type == 'DOPESHEET_EDITOR' and hasattr(space, "mode"):
            base_key += f"##mode:{space.mode}"
    return base_key

def get_area_settings(area: bpy.types.Area) -> TimelineSecondsAreaSettings:
    wm = bpy.context.window_manager
    if not hasattr(wm, "timeline_seconds_display_per_area"):
        wm.timeline_seconds_display_per_area = {}

    big_key = get_area_key(area)
    item = wm.timeline_seconds_display_per_area.get(big_key)
    if item is None:
        if isinstance(wm.timeline_seconds_display_per_area, dict):
            wm.timeline_seconds_display_per_area = bpy.props.CollectionProperty(type=TimelineSecondsAreaSettings)
        item = wm.timeline_seconds_display_per_area.add()
        item.name = big_key
    return item

def to_dict(subsettings):
    result = {}
    for k in subsettings.__annotations__.keys():
        value = getattr(subsettings, k)
        if hasattr(value, "__iter__") and not isinstance(value, (str, bytes)):
            result[k] = list(value)
        else:
            result[k] = value
    return result

def save_preset(path):
    settings = bpy.context.scene.timeline_tick_settings_master
    data = {
        "mode": settings.mode,
        "offset_start_frame_enabled": settings.offset_start_frame_enabled,
        "top": to_dict(settings.top),
        "bottom": to_dict(settings.bottom),
    }
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def load_preset(path):
    if not os.path.exists(path):
        return
    with open(path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    settings = bpy.context.scene.timeline_tick_settings_master
    settings.mode = data.get("mode", "BOTTOM")
    settings.offset_start_frame_enabled = data.get("offset_start_frame_enabled", False)
    for section, prop in (("top", settings.top), ("bottom", settings.bottom)):
        section_data = data.get(section, {})
        for key, value in section_data.items():
            if hasattr(prop, key):
                setattr(prop, key, value)

def load_preset_on_startup():
    load_preset(default_preset_path)
class SaveTimelinePreset(bpy.types.Operator):
    bl_idname = "timeline.save_preset"
    bl_label = "Save"
    def execute(self, context):
        save_preset(default_preset_path)
        self.report({'INFO'}, "Preset saved!")
        return {'FINISHED'}

class ExportTimelinePreset(bpy.types.Operator):
    bl_idname = "timeline.export_preset"
    bl_label = "Export"
    filepath: bpy.props.StringProperty(subtype="FILE_PATH")

    def execute(self, context):
        save_preset(self.filepath)
        self.report({'INFO'}, f"Export complete: {self.filepath}")
        return {'FINISHED'}

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

class ImportTimelinePreset(bpy.types.Operator):
    bl_idname = "timeline.import_preset"
    bl_label = "Import"
    filepath: bpy.props.StringProperty(subtype="FILE_PATH")

    def execute(self, context):
        load_preset(self.filepath)
        self.report({'INFO'}, f"Import Complete: {self.filepath}")
        return {'FINISHED'}

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

class TIMELINE_PT_TickPanel(bpy.types.Panel):
    bl_label = "Timeline seconds display"
    bl_idname = "TIMELINE_PT_TickPanel"
    bl_space_type = 'TOPBAR'
    bl_region_type = 'WINDOW'
    bl_category = ""
    bl_ui_units_x = 0

    def draw(self, context):
        draw_tick_panel(self, context)

# 🔥 プルダウンUI：エリア別モードと全体オプションを分ける
def draw_tick_panel(self, context):
    layout = self.layout
    master = context.scene.timeline_tick_settings_master
    area_settings = get_area_settings(context.area)
    props = master.top if area_settings.mode == 'TOP' else master.bottom

    row = layout.row(align=True)
    row.operator("timeline.save_preset", text="", icon="FILE_TICK")
    row.operator("timeline.export_preset", text="", icon="EXPORT")
    row.operator("timeline.import_preset", text="", icon="IMPORT")

    layout.separator()

    # エリア設定
    layout.label(text="Area setting", icon='SETTINGS')
    layout.prop(area_settings, "mode", text="Position")

    layout.separator()

    # 全体設定
    layout.label(text="Base frame setting", icon='SORTTIME') 
    layout.prop(master, "offset_start_frame_enabled", text="Use rendering range")
    baseframe = context.scene.baseframe_settings
    layout.prop(baseframe, "use_baseframe_offset")
    layout.prop(baseframe, "baseframe_offset_value")

    layout.separator()
    
    layout.label(text="CustomUI", icon='TOOL_SETTINGS')


    if props.enabled:
        layout.prop(props, "base_offset")
        layout.prop(props, "tick_scale")
        layout.prop(props, "main_tick_height")
        layout.prop(props, "sub_tick_height")
        layout.prop(props, "subdivisions")
        layout.prop(props, "label_offset")
        layout.prop(props, "label_size")
        layout.prop(props, "color_main")
        layout.prop(props, "color_sub")
        layout.prop(props, "color_text")
def draw_timeline_seconds_menu(self, context):
    layout = self.layout
    area = context.area
    area_settings = get_area_settings(area)

    layout.separator()
    layout.prop(area_settings, "enabled", text="", icon="EVENT_T", emboss=True)
    layout.popover(panel="TIMELINE_PT_TickPanel", text="", icon='NONE')

def draw_timeline_seconds():
    context = bpy.context
    current_area = context.area
    current_region = context.region
    scene = context.scene
    master = scene.timeline_tick_settings_master

    if hasattr(scene, "baseframe_settings"):
        bfs = scene.baseframe_settings
        use_baseframe_offset = bfs.use_baseframe_offset
        baseframe_offset_value = bfs.baseframe_offset_value
    else:
        use_baseframe_offset = False
        baseframe_offset_value = 0

    offset_start_frame_enabled = master.offset_start_frame_enabled  # ここは今まで通りTickMasterSettingsから取る

    frame_offset = 0
    if offset_start_frame_enabled:
        frame_offset = scene.frame_start
    if use_baseframe_offset:
        frame_offset += baseframe_offset_value

    if not current_area or not current_region:
        return
    master = context.scene.timeline_tick_settings_master
    if not master:
        return
    if current_area.type not in {'DOPESHEET_EDITOR', 'GRAPH_EDITOR', 'NLA_EDITOR'}:
        return
    area_settings = get_area_settings(current_area)
    if not area_settings.enabled:
        return
    props = master.top if area_settings.mode == 'TOP' else master.bottom
    if not props.enabled:
        return
    if current_region.type != 'WINDOW':
        return
    if current_region.width < 1 or current_region.height < 1:
        return

    if area_settings.mode == 'TOP':
        fixed_y = current_region.height - props.base_offset
        direction = -1
    else:
        fixed_y = props.base_offset
        direction = 1

    fps = context.scene.render.fps / context.scene.render.fps_base
    
    v2d = current_region.view2d
    
    view_start = v2d.region_to_view(0, 0)[0] - frame_offset
    view_end = v2d.region_to_view(current_region.width, 0)[0] - frame_offset

    total_seconds = (view_end - view_start) / fps

    interval = 1
    if total_seconds > 1000: interval = 120
    elif total_seconds > 500: interval = 60
    elif total_seconds > 200: interval = 30
    elif total_seconds > 100: interval = 10
    elif total_seconds > 50: interval = 5
    elif total_seconds > 20: interval = 2

    import math
    start_sec = math.floor(view_start / fps / interval) * interval
    end_sec = math.ceil(view_end / fps / interval) * interval

    main_height = props.main_tick_height * props.tick_scale
    sub_height_base = props.sub_tick_height * props.tick_scale

    def premultiply(color):
        r, g, b, a = color
        if a == 0.0:
            return [0.0, 0.0, 0.0, 0.0]
        else:
            return [r * a, g * a, b * a, a]

    premultiplied_main = premultiply(props.color_main)
    premultiplied_sub = premultiply(props.color_sub)

    gpu.state.blend_set('ALPHA_PREMULT')

    for second in range(start_sec, end_sec + 1, interval):
        frame_val = (second * fps) + frame_offset
        x_pos, _ = v2d.view_to_region(frame_val, 0, clip=False)

        coords = [(x_pos, fixed_y), (x_pos, fixed_y + direction * main_height)]
        batch = batch_for_shader(shader, 'LINES', {"pos": coords})
        shader.bind()
        shader.uniform_float("color", premultiplied_main)
        batch.draw(shader)

        label_y = fixed_y + direction * (main_height + props.label_offset)
        blf.position(0, x_pos + 2, label_y, 0)
        blf.size(0, props.label_size)
        blf.color(0, *props.color_text)
        blf.draw(0, f"{second}s")

        if props.subdivisions > 0:
            for i in range(1, props.subdivisions):
                ratio = i / props.subdivisions
                sub_sec = second + interval * ratio
                if sub_sec >= end_sec:
                    continue
                frame_sub = (sub_sec * fps) + frame_offset
                x_sub, _ = v2d.view_to_region(frame_sub, 0, clip=False)

                if abs(ratio - 0.5) < 0.01:
                    sub_height = sub_height_base * 0.7
                else:
                    sub_height = sub_height_base * 0.5

                coords = [(x_sub, fixed_y), (x_sub, fixed_y + direction * sub_height)]
                batch = batch_for_shader(shader, 'LINES', {"pos": coords})
                shader.bind()
                shader.uniform_float("color", premultiplied_sub)
                batch.draw(shader)

    gpu.state.blend_set('NONE')
def delayed_register_draw_handlers():
    global handle_map
    handle_map['DOPESHEET'] = bpy.types.SpaceDopeSheetEditor.draw_handler_add(
        draw_timeline_seconds, (), 'WINDOW', 'POST_PIXEL'
    )
    handle_map['GRAPH'] = bpy.types.SpaceGraphEditor.draw_handler_add(
        draw_timeline_seconds, (), 'WINDOW', 'POST_PIXEL'
    )
    handle_map['NLA'] = bpy.types.SpaceNLA.draw_handler_add(
        draw_timeline_seconds, (), 'WINDOW', 'POST_PIXEL'
    )

def register():
    global handle_map
    bpy.utils.register_class(BaseframeSettings)
    bpy.utils.register_class(TickSubSettings)
    bpy.utils.register_class(TickMasterSettings)
    bpy.utils.register_class(TimelineSecondsAreaSettings)
    bpy.utils.register_class(SaveTimelinePreset)
    bpy.utils.register_class(ExportTimelinePreset)
    bpy.utils.register_class(ImportTimelinePreset)
    bpy.utils.register_class(TIMELINE_PT_TickPanel)

    bpy.types.Scene.baseframe_settings = bpy.props.PointerProperty(type=BaseframeSettings)
    bpy.types.Scene.timeline_tick_settings_master = bpy.props.PointerProperty(type=TickMasterSettings)
    bpy.types.WindowManager.timeline_seconds_display_per_area = bpy.props.CollectionProperty(type=TimelineSecondsAreaSettings)

    bpy.types.TIME_MT_editor_menus.append(draw_timeline_seconds_menu)
    bpy.types.DOPESHEET_MT_editor_menus.append(draw_timeline_seconds_menu)
    bpy.types.GRAPH_MT_editor_menus.append(draw_timeline_seconds_menu)
    bpy.types.NLA_MT_editor_menus.append(draw_timeline_seconds_menu)

    delayed_register_draw_handlers()
    bpy.app.timers.register(load_preset_on_startup, first_interval=1.0)

def unregister():
    global handle_map
    
    del bpy.types.Scene.baseframe_settings

    bpy.types.TIME_MT_editor_menus.remove(draw_timeline_seconds_menu)
    bpy.types.DOPESHEET_MT_editor_menus.remove(draw_timeline_seconds_menu)
    bpy.types.GRAPH_MT_editor_menus.remove(draw_timeline_seconds_menu)
    bpy.types.NLA_MT_editor_menus.remove(draw_timeline_seconds_menu)

    for space, handler in handle_map.items():
        if space == 'DOPESHEET':
            bpy.types.SpaceDopeSheetEditor.draw_handler_remove(handler, 'WINDOW')
        elif space == 'GRAPH':
            bpy.types.SpaceGraphEditor.draw_handler_remove(handler, 'WINDOW')
        elif space == 'NLA':
            bpy.types.SpaceNLA.draw_handler_remove(handler, 'WINDOW')
    handle_map.clear()

    del bpy.types.Scene.timeline_tick_settings_master
    del bpy.types.WindowManager.timeline_seconds_display_per_area

    bpy.utils.unregister_class(BaseframeSettings)
    bpy.utils.unregister_class(TickSubSettings)
    bpy.utils.unregister_class(TickMasterSettings)
    bpy.utils.unregister_class(TimelineSecondsAreaSettings)
    bpy.utils.unregister_class(SaveTimelinePreset)
    bpy.utils.unregister_class(ExportTimelinePreset)
    bpy.utils.unregister_class(ImportTimelinePreset)
    bpy.utils.unregister_class(TIMELINE_PT_TickPanel)

if __name__ == "__main__":
    register()
