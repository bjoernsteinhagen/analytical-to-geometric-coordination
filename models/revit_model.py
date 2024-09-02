from typing import List
import numpy as np
import trimesh
from specklepy.objects import Base
from specklepy.api.models import Branch
from specklepy.transports.server import ServerTransport
from specklepy.core.api import operations


class RevitWall:
    """Encapsulates the wall data, including the mesh and its bounds, ensuring the data is clean and ready for further processing."""
    def __init__(self, mesh: trimesh.Trimesh, wall_id: str):
        self.mesh = mesh  # trimesh.Trimesh object
        self.id = wall_id
        self.bounds = mesh.bounds


class RevitModelProcessor:
    """Responsible for processing the Revit model and extracting architectural walls."""
    def __init__(self, revit_model: Base):
        self.revit_model = revit_model

    def get_architectural_walls(self) -> List[RevitWall]:
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
                    architectural_walls.append(RevitWall(mesh, wall.id))

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
