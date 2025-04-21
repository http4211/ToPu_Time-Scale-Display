bl_info = {
    "name": "ToPu_Viewport Seconds Display",
    "author": "http4211",
    "version": (1, 0, 0),
    "blender": (4, 0, 0),
    "location": "3D Viewport Editor Menus",
    "description": "Display seconds in 3D Viewport with frame-based timing, optimized saving, and remembering last position.",
    "category": "3D View",
}

import bpy
import gpu
import blf
import json
import os
from gpu_extras.batch import batch_for_shader

shader = gpu.shader.from_builtin('UNIFORM_COLOR')
handle_map = {}
save_timer = None
last_saved_data = None
addon_dir = os.path.dirname(__file__)
settings_file_path = os.path.join(addon_dir, "viewport_seconds_display_settings.json")

# --- デフォルト値をまとめたデータ構造
default_data = {
    'position_defaults': {
        'BOTTOM_LEFT': {
            "offset_x": 210,
            "offset_y": 60,
            "font_size": 16,
            "text_color": [1, 1, 1, 1],
            "use_render_start": False,
            "draw_background": True,
            "background_color": [0.9, 0.1, 0.1, 0.3],
            "background_padding": 8,
            "use_minute_display": True
        },
        'BOTTOM_RIGHT': {
            "offset_x": 210,
            "offset_y": 60,
            "font_size": 16,
            "text_color": [1, 1, 1, 1],
            "use_render_start": False,
            "draw_background": True,
            "background_color": [0.9, 0.1, 0.1, 0.3],
            "background_padding": 8,
            "use_minute_display": True
        },
        'TOP_LEFT': {
            "offset_x": 210,
            "offset_y": 60,
            "font_size": 16,
            "text_color": [1, 1, 1, 1],
            "use_render_start": False,
            "draw_background": True,
            "background_color": [0.9, 0.1, 0.1, 0.3],
            "background_padding": 8,
            "use_minute_display": True
        },
        'TOP_RIGHT': {
            "offset_x": 210,
            "offset_y": 30,
            "font_size": 16,
            "text_color": [1, 1, 1, 1],
            "use_render_start": False,
            "draw_background": True,
            "background_color": [0.9, 0.1, 0.1, 0.3],
            "background_padding": 8,
            "use_minute_display": True
        }
    },
    'last_position': 'TOP_LEFT',
}

def update_use_render_start(self, context):
    if self.use_render_start:
        self.use_baseframe_offset = False
    update_position_defaults(self, context)  # ← 位置保存も忘れずに！

def update_use_baseframe_offset(self, context):
    if self.use_baseframe_offset:
        self.use_render_start = False
    update_position_defaults(self, context)  # ← 位置保存も忘れずに！


def save_defaults():
    global last_saved_data
    try:
        json_str = json.dumps(default_data, indent=4)
        if json_str != last_saved_data:
            with open(settings_file_path, "w", encoding="utf-8") as f:
                f.write(json_str)
            last_saved_data = json_str
            print("設定が保存されました")
    except Exception as e:
        print(f"デフォルト設定保存失敗: {e}")

def load_defaults():
    global default_data, last_saved_data
    if not os.path.exists(settings_file_path):
        save_defaults()
        return
    try:
        with open(settings_file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, dict):
                default_data.update(data)
                last_saved_data = json.dumps(default_data, indent=4)
    except Exception as e:
        print(f"デフォルト設定読み込み失敗: {e}")
def delayed_save():
    global save_timer
    save_defaults()
    save_timer = None
    return None

def update_position_defaults(self, context):
    global save_timer
    pos = self.position

    settings = self

    if settings.use_render_start and settings.use_baseframe_offset:
        # 両方同時にONになったら、後からONにした方を優先する
        if context.active_operator and context.active_operator.bl_idname == "wm.context_toggle":
            if context.active_operator.data_path.endswith("use_render_start"):
                settings.use_baseframe_offset = False
            elif context.active_operator.data_path.endswith("use_baseframe_offset"):
                settings.use_render_start = False

    default_data['position_defaults'][pos] = {
        "offset_x": self.offset_x,
        "offset_y": self.offset_y,
        "font_size": self.font_size,
        "text_color": [min(1.0, max(0.0, v)) for v in self.text_color],
        "use_render_start": self.use_render_start,
        "draw_background": self.draw_background,
        "background_color": [min(1.0, max(0.0, v)) for v in self.background_color],
        "background_padding": self.background_padding,
        "use_minute_display": self.use_minute_display,
    }

    if save_timer:
        try:
            bpy.app.timers.unregister(save_timer)
        except ValueError:
            pass
    save_timer = bpy.app.timers.register(delayed_save, first_interval=2.0)

def on_position_change(self, context):
    global default_data, save_timer
    pos = self.position

    # ★ここで切り替えた位置を記憶する
    default_data['last_position'] = pos

    # ★保存されている設定をそのまま読み込む
    defaults = default_data['position_defaults'].get(pos, None)
    if defaults:
        for key, value in defaults.items():
            if hasattr(self, key):
                setattr(self, key, value)

    # ★変更したら保存も予約する
    if save_timer:
        try:
            bpy.app.timers.unregister(save_timer)
        except ValueError:
            pass
    save_timer = bpy.app.timers.register(delayed_save, first_interval=2.0)
def draw_callback():
    context = bpy.context
    area = context.area
    region = context.region
    if not area or not region or area.type != 'VIEW_3D':
        return

    settings = get_area_settings(area)
    if not settings.enabled:
        return

    scene = context.scene
    frame = scene.frame_current
    fps = scene.render.fps / scene.render.fps_base

    if settings.use_render_start:
        seconds = (frame - scene.frame_start) / fps
    elif settings.use_baseframe_offset:
        base_offset = getattr(scene.baseframe_settings, "baseframe_offset_value", 0)
        seconds = (frame - base_offset) / fps
    else:
        seconds = frame / fps


    if settings.use_minute_display:
        minutes = int(seconds // 60)
        seconds_remain = seconds % 60
        time_str = f"{minutes:02}:{seconds_remain:05.2f}"
    else:
        time_str = f"{seconds:.2f}s"

    x = settings.offset_x
    y = settings.offset_y

    if settings.position == 'BOTTOM_RIGHT':
        x = region.width - settings.offset_x - 200
    elif settings.position == 'TOP_LEFT':
        y = region.height - settings.offset_y - 30
    elif settings.position == 'TOP_RIGHT':
        x = region.width - settings.offset_x - 200
        y = region.height - settings.offset_y - 30

    font_id = 0

    if settings.draw_background:
        blf.size(font_id, settings.font_size)
        text_width, text_height = blf.dimensions(font_id, time_str)
        pad = settings.background_padding
        box_coords = (
            (x, y),
            (x + text_width + pad * 2, y),
            (x + text_width + pad * 2, y + text_height + pad * 2),
            (x, y + text_height + pad * 2),
        )
        batch = batch_for_shader(shader, 'TRI_FAN', {"pos": box_coords})
        gpu.state.blend_set('ALPHA')
        shader.bind()
        shader.uniform_float("color", settings.background_color)
        batch.draw(shader)
        gpu.state.blend_set('NONE')

    blf.position(font_id, x + settings.background_padding, y + settings.background_padding, 0)
    blf.size(font_id, settings.font_size)
    blf.color(font_id, *settings.text_color)
    blf.draw(font_id, time_str)
# --- エリアごとの設定を持つクラス ---
class ViewportSecondsSettings(bpy.types.PropertyGroup):
    name: bpy.props.StringProperty()
    enabled: bpy.props.BoolProperty(name="Enable seconds display", default=False)
    position: bpy.props.EnumProperty(
        name="position",
        items=[
            ('BOTTOM_LEFT', "Bottom Left", ""),
            ('BOTTOM_RIGHT', "Bottom Right", ""),
            ('TOP_LEFT', "Top Left", ""),
            ('TOP_RIGHT', "Top Right", ""),
        ],
        default='BOTTOM_LEFT',
        update=on_position_change  # ★ここで切り替え時に保存とロード
    )
    offset_x: bpy.props.IntProperty(name="X offset", default=20, min=-1000, max=1000, update=update_position_defaults)
    offset_y: bpy.props.IntProperty(name="Y offset", default=20, min=-1000, max=1000, update=update_position_defaults)
    font_size: bpy.props.IntProperty(name="Font size", default=16, min=6, max=100, update=update_position_defaults)
    text_color: bpy.props.FloatVectorProperty(
        name="Text color",
        subtype='COLOR',
        size=4,
        default=(1, 1, 1, 1),
        min=0.0, max=1.0,
        update=update_position_defaults
    )
    use_render_start: bpy.props.BoolProperty(
        name="Use rendering range",
        default=False,
        update=update_use_render_start  # ← 個別の関数に！
    )

    use_baseframe_offset: bpy.props.BoolProperty(
        name="Use base frame offset",
        default=False,
        update=update_use_baseframe_offset  # ← 個別の関数に！
    )

    draw_background: bpy.props.BoolProperty(name="Show background box", default=True, update=update_position_defaults)
    background_color: bpy.props.FloatVectorProperty(
        name="Background color",
        subtype='COLOR',
        size=4,
        default=(0, 0, 0, 0.5),
        min=0.0, max=1.0,
        update=update_position_defaults
    )
    background_padding: bpy.props.IntProperty(name="background padding", default=8, min=0, max=50, update=update_position_defaults)
    use_minute_display: bpy.props.BoolProperty(name="Switch display type", default=False, update=update_position_defaults)

# --- エリア設定取得 ---
def get_area_key(area: bpy.types.Area) -> str:
    return str(area.as_pointer())

def get_area_settings(area: bpy.types.Area) -> ViewportSecondsSettings:
    wm = bpy.context.window_manager
    if not hasattr(wm, "viewport_seconds_display_per_area"):
        wm.viewport_seconds_display_per_area = bpy.props.CollectionProperty(type=ViewportSecondsSettings)

    key = get_area_key(area)
    collection = wm.viewport_seconds_display_per_area

    for item in collection:
        if item.name == key:
            return item

    item = collection.add()
    item.name = key

    # 先に position をセットする
    item.position = default_data.get('last_position', 'BOTTOM_LEFT')

    # positionに合わせた設定をロードする
    defaults = default_data['position_defaults'].get(item.position, {})
    for key, value in defaults.items():
        if hasattr(item, key):
            setattr(item, key, value)

    return item

# --- UIパネル ---
class VIEW3D_PT_SecondsDisplayPanel(bpy.types.Panel):
    bl_label = "Seconds display setting"
    bl_idname = "VIEW3D_PT_seconds_display_panel"
    bl_space_type = 'TOPBAR'
    bl_region_type = 'WINDOW'
    bl_ui_units_x = 0

    def draw(self, context):
        layout = self.layout
        area = context.area
        settings = get_area_settings(area)

        layout.label(text="Area setting", icon='SETTINGS')
        layout.prop(settings, "position", text="position")

        layout.separator()

        layout.label(text="Base frame setting", icon='SORTTIME') 

        layout.prop(settings, "use_render_start", text="Use rendering range")

        # baseframe_offset が存在する場合のみ表示
        if hasattr(context.scene, "baseframe_settings") and hasattr(context.scene.baseframe_settings, "baseframe_offset_value"):
            layout.prop(settings, "use_baseframe_offset", text="Use base frame offset")

        layout.separator()

        layout.label(text="CustomUI", icon='TOOL_SETTINGS')

        layout.prop(settings, "offset_x", text="X offset")
        layout.prop(settings, "offset_y", text="Y offset")
        layout.prop(settings, "font_size", text="Font size")
        layout.prop(settings, "text_color", text="Text color")
        layout.prop(settings, "draw_background", text="Show background box")
        layout.prop(settings, "background_color", text="Background color")
        layout.prop(settings, "background_padding", text="Background padding")
        layout.prop(settings, "use_minute_display", text="Switch display type")


# --- ヘッダーメニューに追加 ---
def draw_seconds_display_menu(self, context):
    layout = self.layout
    area = context.area
    settings = get_area_settings(area)

    row = layout.row(align=True)
    row.label(text="")
    row.prop(settings, "enabled", text="", icon="EVENT_T", emboss=True)
    row.popover(panel="VIEW3D_PT_seconds_display_panel", text="", icon='NONE')

# --- 登録・解除 ---
def delayed_register_draw_handlers():
    global handle_map
    handle_map['VIEW_3D'] = bpy.types.SpaceView3D.draw_handler_add(draw_callback, (), 'WINDOW', 'POST_PIXEL')

def register():
    global handle_map
    bpy.utils.register_class(ViewportSecondsSettings)
    bpy.utils.register_class(VIEW3D_PT_SecondsDisplayPanel)

    bpy.types.WindowManager.viewport_seconds_display_per_area = bpy.props.CollectionProperty(type=ViewportSecondsSettings)
    bpy.types.VIEW3D_MT_editor_menus.append(draw_seconds_display_menu)

    load_defaults()
    delayed_register_draw_handlers()

def unregister():
    global handle_map
    bpy.types.VIEW3D_MT_editor_menus.remove(draw_seconds_display_menu)

    if 'VIEW_3D' in handle_map:
        bpy.types.SpaceView3D.draw_handler_remove(handle_map['VIEW_3D'], 'WINDOW')
    handle_map.clear()

    del bpy.types.WindowManager.viewport_seconds_display_per_area

    bpy.utils.unregister_class(ViewportSecondsSettings)
    bpy.utils.unregister_class(VIEW3D_PT_SecondsDisplayPanel)

if __name__ == "__main__":
    register()
