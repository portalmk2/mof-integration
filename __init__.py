bl_info = {
    "name": "Ministry of Flat Integration",
    "author": "Symphonie",
    "description": "Integrate Ministry of Flat into Blender for UV operations",
    "version": (0, 5, 2),
    "blender": (4, 3, 0),
    "category": "UV",
}

# blender_mof_integration.py

import bpy
import subprocess
import os
import tempfile
import pathlib

from bpy.props import IntProperty, EnumProperty
from mathutils import *

# Preference settings to specify the path of the MoF executable
class MOF_AddonPreferences(bpy.types.AddonPreferences):
    bl_idname = __package__

    mof_executable: bpy.props.StringProperty(
        name="Executable Path",
        subtype='FILE_PATH',
        update=lambda self, context: self.correct_executable_path(),
    )

    def draw(self, context):
        layout = self.layout
        layout.label(text="The path of `UnWrapConsole3.exe`")
        layout.prop(self, "mof_executable")

    def correct_executable_path(self):
        """
        Corrects the mof_executable path if it's not pointing to 'UnWrapConsole3.exe'.
        """
        if not self.mof_executable:
            return

        path = pathlib.Path(self.mof_executable)
        
        if not path.exists():
            self.mof_executable = ""
            return
        
        if path.is_file() and path.name != "UnWrapConsole3.exe":
            # If a file, but not the right one, try to find the correct one in the same directory
            parent_dir = path.parent
            correct_executable = parent_dir / "UnWrapConsole3.exe"
            if correct_executable.exists():
                self.mof_executable = str(correct_executable)
            else:
                self.mof_executable = ""
                print(f"Warning: 'UnWrapConsole3.exe' not found in the directory of the chosen executable.")
        elif path.is_dir():
            # if path is a dir, check if it contains "UnWrapConsole3.exe"
            correct_executable = path / "UnWrapConsole3.exe"
            if correct_executable.exists():
                self.mof_executable = str(correct_executable)
            else:
                self.mof_executable = ""
                print(f"Warning: 'UnWrapConsole3.exe' not found in the chosen directory.")
        else:
            self.mof_executable = ""
            
        if self.mof_executable == "":
            bpy.ops.wm.redraw_timer(type='DRAW_WIN_SWAP', iterations=1)
        

def toggle_option_line(layout: bpy.types.UILayout, toggle_id_data: bpy.types.ID, toggle_prop: str, option_list: list[tuple[str, str]]):
    row = layout.row(align=True)
    row.prop(toggle_id_data, toggle_prop, toggle=True)

    col = row.column(align=True)
    col.enabled = getattr(toggle_id_data, toggle_prop)
    for option_id_data, option_prop in option_list:
        col.prop(option_id_data, option_prop)

# Operator to run MoF
class UV_OT_MoFUnwrap(bpy.types.Operator):
    bl_idname = "uv.mof_unwrap"
    bl_label = "Unwrap"
    bl_description = "Automatic unwrap with Ministry of Flat"
    bl_options = {'REGISTER', 'UNDO'}

    texture_resolution: bpy.props.IntProperty(
        name="Texture Resolution",
        description='Resolution of texture, to give right amount of island gaps to prevent bleeds.',
        default=1024,
        min=128,
        max=8192,
    )

    separate_hard_edge: bpy.props.BoolProperty(
        name="Separate Hard Edges",
        description='Guarantees that all hard edges are separated. Useful for lightmapping and Normalmapping',
        default=False,
    )

    aspect_ratio: bpy.props.FloatProperty(
        name="Aspect Ratio",
        description='Aspect ratio of pixels. For non square textures.',
        default=1.0,
        min=0.0,
        max=10.0,
    )

    use_normal: bpy.props.BoolProperty(
        name='Use Normal',
        description='Use the models normals to help classify polygons.',
        default=False,
    )

    overlap_identical_parts: bpy.props.BoolProperty(
        name='Overlap Identical parts',
        description='Overlap identtical parts to take up the same texture space.',
        default=False,
    )
    
    overlap_mirrored_parts: bpy.props.BoolProperty(
        name='Overlap mirrored parts',
        description='Overlap mirrored parts to take up the same texture space.',
        default=False,
    )
    
    scale_uv_space_to_worldspace: bpy.props.BoolProperty(
        name='Scale UV space to worldspace',
        description='Scales the UVs to match their real world scale going beyound the zero to one range.',
        default=False,
    )

    texture_density: bpy.props.IntProperty(
        name="Texture Density",
        description='If worldspace is enabled, this value sets the number of pixels per unit.',
        default=1024,
        min=128,
        max=8192,
    )

    seam_direction: bpy.props.FloatVectorProperty(
        name="Seam Direction",
        description='Sets a pointy in space that seams are directed towards. By default the center of the model.',
        default=(0.0, 0.0, 0.0),
        subtype='XYZ',
        size=3,
    )

    cones: bpy.props.BoolProperty(
        name='Cones',
        description='Searches the model for sharp Cones.',
        default=True,
    )

    cone_ratio: bpy.props.FloatProperty(
        name="Cone Ratio",
        description='The minimum ratio of a triangle used in a cone.',
        default=0.5,
        min=0.0,
        max=1.0,
    )

    strips: bpy.props.BoolProperty(
        name='Strips',
        description='Searches the model for strips of quads.',
        default=True,
    )

    grids: bpy.props.BoolProperty(
        name='Grids',
        description='Searches the model for grids of quads.',
        default=True,
    )

    patches: bpy.props.BoolProperty(
        name='Patches',
        description='Searches the model for grids of quads.',
        default=True,
    )

    planes: bpy.props.BoolProperty(
        name='Planes',
        description='Detect planes.',
        default=True,
    )

    flatness: bpy.props.FloatProperty(
        name="Flatness",
        description='Minimum normal dot product between two flat polygons.',
        default=0.9,
        min=-1.0,
        max=1.0,
    )

    merge: bpy.props.BoolProperty(
        name='Merge',
        description='Merges polygons using unfolding',
        default=True,
    )

    merge_limit: bpy.props.FloatProperty(
        name="Merge Limit",
        description='Limit the angle of polygons beeing merged.',
        default=0.0,
    )

    pre_smooth: bpy.props.BoolProperty(
        name='Pre-Smooth',
        description='Soften the mesh before atempting to cut and project.',
        default=True,
    )

    soft_unfold: bpy.props.BoolProperty(
        name='Soft Unfold',
        description='Atempt to unfold soft surfaces.',
        default=True,
    )

    tubes: bpy.props.BoolProperty(
        name='Tubes',
        description='Find tube shaped geometry and unwrap it using cylindrical projection.',
        default=True,
    )

    junctions: bpy.props.BoolProperty(
        name='Junctions',
        description='Find and handle Junctions between tubes.',
        default=True,
    )

    extra_ordinary_point: bpy.props.BoolProperty(
        name='Extra Ordinary Point',
        description='Using vertices not sharded by 4 quads as starting points for cutting.',
        default=False,
    )

    angle_based_flatening: bpy.props.BoolProperty(
        name='Angle Based Flatening',
        description='Using angle based flatening.',
        default=True,
    )

    smooth: bpy.props.BoolProperty(
        name='Smooth',
        description='Cut and project smooth surfaces.',
        default=True,
    )

    repair_smooth: bpy.props.BoolProperty(
        name='Repair Smooth',
        description='Attaches small islands to larger islands on smooth surfaces.',
        default=True,
    )

    repair: bpy.props.BoolProperty(
        name='Repair',
        description='Repair edges to make then straight.',
        default=True,
    )

    squares: bpy.props.BoolProperty(
        name='Squares',
        description='Finds various individual polygons that hare right angles.',
        default=True,
    )

    relax: bpy.props.BoolProperty(
        name='Relax',
        description='Relax all smooth polygons to minimize distortion.',
        default=True,
    )

    relax_iterations: bpy.props.IntProperty(
        name="Relax Iterations",
        description='The number of iteration loops when relaxing.',
        default=50,
        min=0,
        max=1000,
    )

    expand: bpy.props.FloatProperty(
        name="Expand",
        description='Expand soft surfaces to make more use of texture space. Experimental, off by default',
        default=0.25,
    )

    cut: bpy.props.BoolProperty(
        name='Cut',
        description='Cut down awkward shapes in order to optimize layout coverage.',
        default=True,
    )

    stretch: bpy.props.BoolProperty(
        name='Stretch',
        description='Stretch any island that is too wide to fit in the image.',
        default=True,
    )

    match: bpy.props.BoolProperty(
        name='Match',
        description='Match individual tirangles for better packing.',
        default=True,
    )

    packing: bpy.props.BoolProperty(
        name='Packing',
        description='Pack islands in to a rectangle',
        default=True,
    )

    rasterization: bpy.props.IntProperty(
        name="Rasterization",
        description='Resolution of packing rasterization.',
        default=64,
        min=1,
        max=1024,
    )

    packing_iterations: bpy.props.IntProperty(
        name="Packing Iterations",
        description='How many times the packer will pack the islands in order to find the optimal island spaceing.',
        default=4,
        min=1,
        max=100,
    )

    scale_to_fit: bpy.props.FloatProperty(
        name="Scale To Fit",
        description='Scales islands to fit cavites.',
        default=0.5,
    )

    validate: bpy.props.BoolProperty(
        name='Validate',
        description='Validate geometry after each stage and print out any issues found (For debugging only).',
        default=False,
    )

    expand_optinos: bpy.props.BoolProperty(
        name='Expand Options',
        description='Expand options',
        default=False,
    )
    auto_reunwrap: bpy.props.BoolProperty(
        name='Auto Re-unwrap',
        description='Invoke Blender\'s unwrapping tool after MoF finishes its work',
        default=True,
    )


    def invoke(self, context, event):
        wm = context.window_manager
        return wm.invoke_props_dialog(self, width=400)


        
    def draw(self, context):
        layout = self.layout
        row = layout.row(align=True)
        row.use_property_split=True
        row.prop(self, "auto_reunwrap")
        layout.prop(self, "expand_optinos", toggle=True, emboss=False, icon='TRIA_DOWN' if self.expand_optinos else 'TRIA_RIGHT', text="Other Options (You don't need them actually)")

        if self.expand_optinos:
            
            layout.label(text="Run Ministry of Flat UV Unwrap with these settings?")
            box = layout.box()
            box.prop(self, "texture_resolution")
            box.prop(self, "separate_hard_edge", toggle=True)
            box.prop(self, "aspect_ratio")
            box.prop(self, "use_normal", toggle=True)
            row1 = box.row(align=True)
            row1.prop(self, "overlap_identical_parts", toggle=True)
            row1.prop(self, "overlap_mirrored_parts", toggle=True)
            toggle_option_line(box, self, "scale_uv_space_to_worldspace", [(self, "texture_density")])
            box.prop(self, "seam_direction")

            
            box.separator()
            shape_col = box.column(align=True)
            shape_box = shape_col.box()
            row1 = shape_box.row(align=True)

            row1.prop(self, "cones", toggle=True)
            row1.prop(self, "grids", toggle=True)
            row1.prop(self, "strips", toggle=True)
            row1.prop(self, "patches", toggle=True)
            row1.prop(self, "planes", toggle=True)
            row1.prop(self, "tubes", toggle=True)
            row1.prop(self, "junctions", toggle=True)
            row1.prop(self, "squares", toggle=True)
            
            shape_box = shape_col.box()


            if self.cones:
                shape_box.prop(self, "cone_ratio")
            if self.planes:
                shape_box.prop(self, "flatness")

            box.separator()
            
            toggle_option_line(box, self, "merge", [(self, "merge_limit")])
            box.prop(self, "pre_smooth", toggle=True)
            box.prop(self, "soft_unfold", toggle=True)
            box.prop(self, "extra_ordinary_point", toggle=True)
            box.prop(self, "angle_based_flatening", toggle=True)
            box.prop(self, "smooth", toggle=True)

            box.prop(self, "repair", toggle=True)
            box.prop(self, "repair_smooth", toggle=True)

            toggle_option_line(box, self, "relax", [(self, "relax_iterations")])

            box.prop(self, "expand", toggle=True)

            row2 = box.row(align=True)
            row2.prop(self, "cut", toggle=True)
            row2.prop(self, "stretch", toggle=True)
            row2.prop(self, "match", toggle=True)

            toggle_option_line(box, self, "packing", [(self, 'rasterization'),(self, "packing_iterations")])
            box.prop(self, "scale_to_fit")
            box.prop(self, "validate", toggle=True)

    def assemble_options_command_line(self) -> list[str]:
        options = []
        def get_bool(opt: bool) -> str:
            return "TRUE" if opt else "FALSE"
        def get_int(opt: int) -> str:
            return str(opt)
        def get_float(opt: float) -> str:
            return str(opt)
        def get_vec3(opt: tuple[float, float, float]|Vector) -> str:
            return " ".join(map(str, opt))

        options.append(f"-RESOLUTION {get_int(self.texture_resolution)}")
        options.append(f"-SEPARATE {get_bool(self.separate_hard_edge)}")
        options.append(f"-ASPECT {get_float(self.aspect_ratio)}")
        options.append(f"-NORMALS {get_bool(self.use_normal)}")
        options.append(f"-OVERLAP {get_bool(self.overlap_identical_parts)}")
        options.append(f"-MIRROR {get_bool(self.overlap_mirrored_parts)}")
        options.append(f"-WORLDSCALE {get_bool(self.scale_uv_space_to_worldspace)}")
        options.append(f"-DENSITY {get_int(self.texture_density)}")
        options.append(f"-CENTER {get_vec3(self.seam_direction)}")

        options.append(f'-CONE {get_bool(self.cones)}')
        options.append(f'-GRIDS {get_bool(self.grids)}')
        options.append(f'-STRIP {get_bool(self.strips)}')
        options.append(f'-PATCH {get_bool(self.patches)}')
        options.append(f'-PLANES {get_bool(self.planes)}')
        options.append(f'-TUBES {get_bool(self.tubes)}')
        options.append(f'-JUNCTIONSDEBUG {get_bool(self.junctions)}')
        options.append(f'-SQUARE {get_bool(self.squares)}')

        options.append(f'-CONERATIO {get_float(self.cone_ratio)}')
        options.append(f'-FLATT {get_float(self.flatness)}')
        

        options.append(f'-MERGE {get_bool(self.merge)}')
        options.append(f'-MERGELIMIT {get_float(self.merge_limit)}')
        options.append(f'-PRESMOOTH {get_bool(self.pre_smooth)}')
        options.append(f'-SOFTUNFOLD {get_bool(self.soft_unfold)}')
        options.append(f'-EXTRADEBUG {get_bool(self.extra_ordinary_point)}')
        options.append(f'-ABF {get_bool(self.angle_based_flatening)}')
        options.append(f'-SMOOTH {get_bool(self.smooth)}')
        options.append(f'-REPAIR {get_bool(self.repair)}')
        options.append(f'-REPAIRSMOOTH {get_bool(self.repair_smooth)}')
        options.append(f'-RELAX {get_bool(self.relax)}')
        options.append(f'-RELAX_ITERATIONS {get_int(self.relax_iterations)}')
        options.append(f'-EXPAND {get_float(self.expand)}')
        options.append(f'-CUTDEBUG {get_bool(self.cut)}')
        options.append(f'-STRETCH {get_bool(self.stretch)}')
        options.append(f'-MATCH {get_bool(self.match)}')
        options.append(f'-PACKING {get_bool(self.packing)}')
        options.append(f'-RASTERIZATION {get_int(self.rasterization)}')
        options.append(f'-PACKING_ITERATIONS {get_int(self.packing_iterations)}')
        options.append(f'-SCALETOFIT {get_float(self.scale_to_fit)}')
        options.append(f'-VALIDATE {get_bool(self.validate)}')

        return options

        
    def execute(self, context):
        obj: bpy.types.Object = context.active_object
        if obj is None or obj.type != 'MESH':
            self.report({'ERROR'}, "No mesh object selected")
            return {'CANCELLED'}

        
        # Get the path of the MoF executable from preferences
        preferences = bpy.context.preferences.addons[__package__].preferences
        mof_exec = preferences.mof_executable

        if not mof_exec:
            self.report({'ERROR'}, "MoF executable path not set or not correct in preferences")
            return {'CANCELLED'}

        if not os.path.isfile(mof_exec) or os.path.basename(mof_exec) != "UnWrapConsole3.exe":
            self.report({'ERROR'}, "MoF executable path is not correct (should be 'UnWrapConsole3.exe')")
            return {'CANCELLED'}
    
        # Save the current mode
        original_mode = bpy.context.mode
        if original_mode == 'EDIT_MESH':
            original_mode = 'EDIT'
    
        # Switch to edit mode
        bpy.ops.object.mode_set(mode='OBJECT')


        bpy.ops.object.select_all(action='DESELECT')
        obj.select_set(True)
        context.view_layer.objects.active = obj
                
    
        # Export the active object to an OBJ file
        with tempfile.NamedTemporaryFile(suffix=".obj", delete=False) as temp_input:
            input_obj_path = temp_input.name
        bpy.ops.wm.obj_export(filepath=input_obj_path, export_selected_objects=True, export_materials=False, export_normals=True)
        
        try:
            # Run MoF
            with tempfile.NamedTemporaryFile(suffix=".obj", delete=False) as temp_output:
                output_obj_path = temp_output.name
            
            imported_obj = None # Initialize to None

            options = self.assemble_options_command_line()
            options = [option.split(' ') for option in options]
            options = [item for sublist in options for item in sublist]

            print(f'MoF {input_obj_path} {output_obj_path} {" ".join(options)}')
            subprocess.run([mof_exec, input_obj_path, output_obj_path] + options)
    
            # Import the output OBJ file
            bpy.ops.wm.obj_import(filepath=output_obj_path)
    
            # Get the imported object
            imported_obj = bpy.context.selected_objects[0]
            
            # Ensure the original object has a UV map
            if not obj.data.uv_layers:
                obj.data.uv_layers.new(name="UVMap")
                
            # Get the active UV channel name from the original object
            selected_uv_channel = obj.data.uv_layers.active.name
            
            # Ensure the imported object has a UV map
            if not imported_obj.data.uv_layers:
                imported_obj.data.uv_layers.new(name=selected_uv_channel)
            else:
                # Rename the first UV channel to match the original object's UV channel
                imported_obj.data.uv_layers[0].name = selected_uv_channel

            # Add a Data Transfer modifier to copy UVs
            data_trans = obj.modifiers.new(name="DataTransfer", type='DATA_TRANSFER')
            data_trans.object = imported_obj
            data_trans.use_loop_data = True
            data_trans.data_types_loops = {'UV'}
            data_trans.loop_mapping = 'NEAREST_POLYNOR'

            with context.temp_override(active_object=obj):
                bpy.ops.object.datalayout_transfer('INVOKE_DEFAULT', data_type='UV')
    
            # Apply the modifier
            bpy.context.view_layer.objects.active = obj
            bpy.ops.object.modifier_apply(modifier=data_trans.name)
            data_trans = None
            
            # Enter edit mode and select all UVs
            bpy.ops.object.mode_set(mode='EDIT')
            bpy.ops.uv.select_all(action='SELECT')
            
            # Run 'Seams from Islands'
            bpy.ops.uv.seams_from_islands()
            
            if self.auto_reunwrap:
                # Run 'Unwrap' (Angle Based)
                bpy.ops.uv.unwrap('INVOKE_DEFAULT', method='ANGLE_BASED', margin=0.001)
                
                # Pack Islands
                bpy.ops.uv.pack_islands(margin=0.001)
    
            self.report({'INFO'}, "MoF integration completed")
    
        finally:
            # Cleanup OBJ files and imported object
            if os.path.exists(input_obj_path):
                os.remove(input_obj_path)
            if os.path.exists(output_obj_path):
                os.remove(output_obj_path)
            if data_trans:
                obj.modifiers.remove(data_trans)
            if imported_obj:
                bpy.data.objects.remove(imported_obj, do_unlink=True)
    
            # Restore the original mode
            with context.temp_override(active_object=obj):
                bpy.ops.uv.select(deselect=True)
                bpy.ops.object.mode_set(mode=original_mode)
                
    
            return {'FINISHED'} # Ensure FINISHED is returned even on error for cleanup

# UI button in the UV editor menu
def menu_func(self, context):
    self.layout.operator(UV_OT_MoFUnwrap.bl_idname, text="Unwrap with Ministry of Flat")

# UI button in the UV editor side panel
class MOF_PT_Panel(bpy.types.Panel):
    bl_label = "Ministry of Flat"
    bl_idname = "UV_PT_mof"
    bl_space_type = 'IMAGE_EDITOR'
    bl_region_type = 'UI'
    bl_category = 'Tool'

    def draw(self, context):
        layout = self.layout
        layout.operator(UV_OT_MoFUnwrap.bl_idname, text = "Unwrap")

# Register the classes and UI elements
def register():
    bpy.utils.register_class(MOF_AddonPreferences)
    bpy.utils.register_class(UV_OT_MoFUnwrap)
    bpy.utils.register_class(MOF_PT_Panel)
    bpy.types.IMAGE_MT_uvs.append(menu_func)

def unregister():
    bpy.types.IMAGE_MT_uvs.remove(menu_func)
    bpy.utils.unregister_class(MOF_PT_Panel)
    bpy.utils.unregister_class(UV_OT_MoFUnwrap)
    bpy.utils.unregister_class(MOF_AddonPreferences)

if __name__ == "__main__":
    register()
