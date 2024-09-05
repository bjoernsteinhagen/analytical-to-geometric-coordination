from typing import List
import numpy as np
import trimesh
from specklepy.objects import Base
from specklepy.api.models import Branch
from specklepy.transports.server import ServerTransport
from specklepy.core.api import operations


class RevitWall:
    """Encapsulates the wall data, including the mesh and its bounds, ensuring the data is clean and ready for further processing."""
    def __init__(self, mesh: trimesh.Trimesh, wall_id: str, buffer_distance: float):
        self.mesh = mesh  # trimesh.Trimesh object
        self.id = wall_id
        self.buffered_mesh = self.create_buffered_mesh(buffer_distance)

    def create_buffered_mesh(self, buffer_distance: float) -> trimesh.Trimesh:
        """Create a slightly larger mesh by moving each vertex along its normal."""
        # Ensure normals are calculated
        if self.mesh.vertex_normals.size == 0:
            self.mesh.compute_vertex_normals()
        
        # Create a copy of the vertices and normals
        vertices = self.mesh.vertices.copy()
        vertex_normals = self.mesh.vertex_normals.copy()

        # Normalize the normals
        norms = np.linalg.norm(vertex_normals, axis=1, keepdims=True)
        normalized_normals = vertex_normals / np.maximum(norms, 1e-10)  # Avoid division by zero

        # Displace the vertices along the normal by the buffer_distance
        buffered_vertices = vertices + buffer_distance * normalized_normals

        # Create a new mesh with the buffered vertices
        buffered_mesh = trimesh.Trimesh(vertices=buffered_vertices, faces=self.mesh.faces, process=False)

        # Optionally, check for watertightness and repair if necessary
        if not buffered_mesh.is_watertight:
            buffered_mesh = buffered_mesh.repair()

        return buffered_mesh
        

class RevitModelProcessor:
    """Responsible for processing the Revit model and extracting architectural walls."""
    def __init__(self, revit_model: Base):
        self.revit_model = revit_model

    def get_architectural_walls(self, buffer_distance) -> List[RevitWall]:
        """Extracts architectural walls from the Revit model.

        Returns:
            List[RevitWall]: A list of RevitWall objects.
        """
        if not hasattr(self.revit_model, "elements"):
            raise AttributeError("The provided Revit model has no 'elements' attribute.")

        collections = self.revit_model.elements
        architectural_walls = []

        for collection in collections:
            if collection.name == 'Walls':
                for wall in collection.elements:
                    if not self._is_valid_wall(wall):
                        continue

                    faces = wall.displayValue[0].faces
                    vertices = wall.displayValue[0].vertices

                    # Prepare the mesh
                    faces_indices = np.array(faces).reshape(-1, 4)[:, 1:]
                    vertices = np.array(vertices).reshape(-1, 3)
                    mesh = trimesh.Trimesh(vertices=vertices, faces=faces_indices)

                    # Create RevitWall instance
                    architectural_walls.append(RevitWall(mesh, wall.id, buffer_distance))

        if not architectural_walls:
            raise ValueError("No architectural walls found in the provided Revit model.")
        
        return architectural_walls

    def _is_valid_wall(self, wall) -> bool:
        """Validates that the wall has the necessary attributes."""
        return (
            hasattr(wall, "displayValue")
            and isinstance(wall.displayValue, list)
            and len(wall.displayValue) > 0
            and hasattr(wall.displayValue[0], "faces")
            and hasattr(wall.displayValue[0], "vertices")
        )

    @staticmethod
    def get_model(speckle_client, project_id, static_model_name: str) -> Base:
        """Retrieves the Revit model from Speckle."""
        remote_transport = ServerTransport(project_id, speckle_client)

        model: Branch = speckle_client.branch.get(project_id, static_model_name, commits_limit=1)
        if not model:
            raise LookupError(f"The static model named '{static_model_name}' does not exist.")

        reference_model_commits = model.commits.items
        if not reference_model_commits:
            raise LookupError("The static model has no versions.")

        latest_reference_model_version_object = reference_model_commits[0].referencedObject

        latest_reference_model_version = operations.receive(
            latest_reference_model_version_object,
            remote_transport,
        )

        return latest_reference_model_version

def export_walls_to_obj(architectural_walls, file_path):
    """Combine all wall meshes and export them to a single .obj file."""
    # List to store all the individual meshes
    meshes = []

    # Iterate through the walls and collect their meshes
    for wall in architectural_walls:
        meshes.append(wall.mesh)

    # Combine all meshes into a single mesh
    combined_mesh = trimesh.util.concatenate(meshes)

    # Export the combined mesh to an .obj file
    combined_mesh.export(file_path, file_type='.obj')