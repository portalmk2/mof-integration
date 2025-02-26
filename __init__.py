bl_info = {
    "name": "Ministry of Flat Integration",
    "author": "Symphonie",
    "description": "Integrate Ministry of Flat into Blender for UV operations",
    "version": (0, 5, 0),
    "blender": (4, 3, 0),
    "category": "UV",
}

# blender_mof_integration.py

import bpy
import subprocess
import os
import tempfile

# Preference settings to specify the path of the MoF executable
class MOF_AddonPreferences(bpy.types.AddonPreferences):
    bl_idname = __package__

    mof_executable: bpy.props.StringProperty(
        name="Executable Path",
        subtype='FILE_PATH',
    )

    def draw(self, context):
        layout = self.layout
        layout.label(text="The path of Ministry of Flat")
        layout.prop(self, "mof_executable")

# Operator to run MoF
class UV_OT_MoFUnwrap(bpy.types.Operator):
    bl_idname = "uv.mof_unwrap"
    bl_label = "Unwrap"
    bl_description = "Automatic unwrap with Ministry of Flat"

    def execute(self, context):
        # Get the active object
        obj = context.active_object
        if obj is None or obj.type != 'MESH':
            self.report({'ERROR'}, "No active mesh object selected")
            return {'CANCELLED'}
        
        # Get the path of the MoF executable from preferences
        preferences = bpy.context.preferences.addons[__package__].preferences
        mof_exec = preferences.mof_executable

        if not mof_exec:
            self.report({'ERROR'}, "MoF executable path not set in preferences")
            return {'CANCELLED'}
    
        # Save the current mode
        original_mode = bpy.context.mode
        if original_mode == 'EDIT_MESH':
            original_mode = 'EDIT'
    
        # Switch to edit mode
        bpy.ops.object.mode_set(mode='OBJECT')
    
        # Export the active object to an OBJ file
        with tempfile.NamedTemporaryFile(suffix=".obj", delete=False) as temp_input:
            input_obj_path = temp_input.name
        bpy.ops.wm.obj_export(filepath=input_obj_path, export_selected_objects=True, export_materials=False)
        
        try:
            # Run MoF
            with tempfile.NamedTemporaryFile(suffix=".obj", delete=False) as temp_output:
                output_obj_path = temp_output.name
            
            imported_obj = None # Initialize to None
            print(f'MoF {input_obj_path} {output_obj_path}')
            subprocess.run([mof_exec, input_obj_path, output_obj_path])
    
            # Import the output OBJ file
            bpy.ops.wm.obj_import(filepath=output_obj_path)
    
            # Get the imported object
            imported_obj = bpy.context.selected_objects[0]
            
            # Rename the UV channel of the imported OBJ file to match the selected UV channel of the original object
            selected_uv_channel = obj.data.uv_layers.active.name
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