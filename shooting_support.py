import os
import glob
from shutil import copyfile, move
import subprocess
from VTK_background import Model, merge_elements
from pathlib import Path
from pericardium_generation import create_pericarium


class MeshTetrahedralization:

    def __init__(self, main_path, models_path, geo_path, temp_path, output_path, k_model, template=False):
        self.main_path = main_path
        self.models_path = models_path
        self.temp_path = temp_path
        self.geo_path = geo_path
        self.output_path = output_path
        self.k_model = k_model
        self.template = template

    def clean(self):
        [f.unlink() for f in Path(self.temp_path).glob("*") if f.is_file()]

    def run_tetrahedralization(self, peri=False):
        if not peri:
            subprocess.call(os.path.join(self.main_path, './meshing.sh'))
        else:
            subprocess.call(os.path.join(self.main_path, './peri_meshing.sh'))

    # --- Copying files
    def copy_surface_mesh_files(self):
        self.clean()
        print(self.models_path)
        if not self.template:
            model_files = glob.glob(os.path.join(self.models_path, 'Shooting_{}_*'.format(self.k_model)))
        else:
            model_files = glob.glob(os.path.join(models_path, '*Template*'))
        print(model_files)
        model_files = [mf for mf in model_files if 'ControlPoints' not in mf and'Momenta' not in mf]
        for mf in model_files:
            copyfile(mf, os.path.join(self.temp_path, os.path.basename(mf)))

    def copy_volumetric_file(self):
        self.clean()
        model_file = os.path.join(self.models_path, 'Full_Heart_{}.vtk'.format(self.k_model))
        copyfile(model_file, os.path.join(self.temp_path, 'Full_Heart.vtk'))

    # --- Modyfing geo (filename)
    def modify_geo_files(self):
        geo_files = glob.glob(os.path.join(self.geo_path, '*.geo'))
        geo_files.sort()
        model_files = glob.glob(os.path.join(self.temp_path, '*'))
        model_files.sort()

        for gf, mf in zip(geo_files, model_files):
            with open(gf, 'r') as file:
                data = file.readlines()
            data[1] = ('Merge "' + mf + '";\n')
            with open(gf, 'w') as file:
                file.writelines(data)

    # --- Tagging and merging-------------------------------------------------------------------------------------------
    def tag_and_merge_heart_elements(self):
        models = []
        tetra_files = [os.path.join(self.main_path, 'tetra', el + '_tetra.vtk') for el in Model.list_of_elements]
        for element in tetra_files:
            print(os.path.basename(element))
            element_name = os.path.basename(element).split('_')[0]
            print(element_name)
            model = Model(element)
            element_tag = [i + 1 for i, elem in enumerate(model.list_of_elements) if elem == element_name][0]
            print('Element name: {}, element tag: {}'.format(element_name, element_tag))
            model.build_tag(label=element_tag)
            model.change_tag_label()
            models.append(model)

        final_model = models.pop(0)
        for model_to_merge in models:
            final_model.mesh = merge_elements(final_model.mesh, model_to_merge.mesh)
        final_model.tetrahedralize()
        final_model.write_vtk(postscript='merged', type_='UG')
        if not self.template:
            os.rename(os.path.join(self.main_path, 'tetra', 'LV_tetramerged.vtk'),
                      os.path.join(self.main_path, 'tetra', 'Full_Heart_{}.vtk'.format(self.k_model)))
            move(os.path.join(self.main_path, 'tetra', 'Full_Heart_{}.vtk'.format(self.k_model)),
                 os.path.join(self.output_path, 'Full_Heart_{}.vtk'.format(self.k_model)))
        else:
            os.rename(os.path.join(self.main_path, 'tetra', 'LV_tetramerged.vtk'),
                      os.path.join(self.main_path, 'tetra', 'Full_Template.vtk'))
            move(os.path.join(self.main_path, 'tetra', 'Full_Template.vtk'),
                 os.path.join(self.output_path, 'Full_Template.vtk'))

    def tag_and_merge_pericardium(self):
        model = Model(os.path.join(self.temp_path, 'Full_Heart.vtk'))
        peri_model = Model(os.path.join(self.temp_path, 'peri_tetra.vtk'))
        peri_tag = len(model.list_of_elements) + 1
        print('Element name: pericardium, element tag: {}'.format(peri_tag))
        peri_model.build_tag(label=peri_tag)
        peri_model.change_tag_label()
        model.mesh = merge_elements(model.mesh, peri_model.mesh)
        model.tetrahedralize()
        model.write_vtk(postscript='_merged', type_='UG')
        os.rename(os.path.join(self.temp_path, 'Full_Heart_merged.vtk'),
                  os.path.join(self.temp_path, 'Full_Heart_{}_w_peri.vtk'.format(self.k_model)))
        move(os.path.join(self.temp_path, 'Full_Heart_{}_w_peri.vtk'.format(self.k_model)),
             os.path.join(self.output_path, 'Full_Heart_{}_w_peri.vtk'.format(self.k_model)))

    # --- Pipelines-----------------------------------------------------------------------------------------------------
    def pipeline_surf_2_tetra_mesh(self):
        self.copy_surface_mesh_files()
        self.modify_geo_files()
        self.run_tetrahedralization()
        self.tag_and_merge_heart_elements()

    def pipeline_add_peri(self):
        self.copy_volumetric_file()
        create_pericarium(os.path.join(self.temp_path, 'Full_Heart.vtk'))
        self.run_tetrahedralization(peri=True)
        self.tag_and_merge_pericardium()

# --- END MeshTetrahedralization----------------------------------------------------------------------------------------


if __name__ == '__main__':

    # TODO: Make sure that the element files of vtk and geo are sorted in the same way in 'modify_geo_files'

    # --- Dataset generation -------------------------------------------------------------------------------------------
    for i in range(40, 41):
        # Path to models, surface or volumetric
        models_path = ('/media/mat/BEDC-845B/'
                       'Surface_meshes/output_shooting_{}/final_steps').format(i)
        output_path = '/media/mat/BEDC-845B/Final_models_{}'.format(str(i).zfill(2))  # Storing path

        if not os.path.exists(output_path):
            os.mkdir(output_path)
        for j in range(25):

            sup = MeshTetrahedralization(main_path='/home/mat/Deformetrica/deterministic_atlas_ct/gmsh',
                                         models_path=models_path,
                                         geo_path='/home/mat/Deformetrica/deterministic_atlas_ct/gmsh/geofiles',
                                         temp_path='/home/mat/Deformetrica/deterministic_atlas_ct/gmsh/current_model',
                                         output_path=output_path,
                                         k_model=j,
                                         template=False)
            sup.pipeline_surf_2_tetra_mesh()

    # --- Pericardium tetrahedralization -------------------------------------------------------------------------------
    # output_path = '/media/mat/BEDC-845B/Models_w_pericardium_4'
    # models_path = '/media/mat/BEDC-845B/Final_models_04'
    # if not os.path.exists(output_path):
    #     os.mkdir(output_path)
    # for j in [24]:  # range(25):
    #     sup = MeshTetrahedralization(main_path='/home/mat/Python/code/CT_mesh_handling/gmsh',
    #                                  models_path=models_path,
    #                                  geo_path='/home/mat/Python/code/CT_mesh_handling/gmsh/geofiles',
    #                                  temp_path='/home/mat/Python/code/CT_mesh_handling/gmsh/current_model',
    #                                  output_path=output_path,
    #                                  k_model=j,
    #                                  template=False)
    #     sup.pipeline_add_peri()
