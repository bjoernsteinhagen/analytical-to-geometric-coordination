import numpy as np
import trimesh

class MeshBufferer:
    """Responsible for creating a buffered mesh."""

    @staticmethod
    def create_buffered_mesh(mesh, buffer_distance=0.01) -> trimesh.Trimesh:
        """Create a slightly larger mesh by moving each vertex along its normal."""
        vertices = mesh.vertices.copy()
        vertex_normals = mesh.vertex_normals.copy()

        buffered_vertices = vertices + buffer_distance * vertex_normals

        buffered_mesh = trimesh.Trimesh(vertices=buffered_vertices, faces=mesh.faces)
        return buffered_mesh


class InteriorPointGenerator:
    """Responsible for generating interior points for a surface."""

    @staticmethod
    def generate_interior_points(surface):
        """Generate a grid of points inside the rectangular surface."""
        min_bound = np.min(surface.points, axis=0)
        max_bound = np.max(surface.points, axis=0)

        # Calculate and return the centroid as a 2D array of shape (1, 3)
        centroid = np.mean([min_bound, max_bound], axis=0)
        return np.array([centroid])


class SurfaceWallMatcher:
    """Responsible for matching analytical surfaces with architectural walls."""

    def __init__(self, buffer_distance=0.01):
        self.buffer_distance = buffer_distance

    def check_surface_wall_match(self, surface, wall) -> bool:
        """Check if an analytical surface matches with an architectural wall."""
        # Create the buffered mesh
        buffered_mesh = MeshBufferer.create_buffered_mesh(wall.mesh, self.buffer_distance)

        # Check if all surface points are within the buffered mesh
        surface_points_array = np.array(surface.points)
        vertices_inside = buffered_mesh.contains(surface_points_array)
        if not np.all(vertices_inside):
            return False

        # Generate and check if all interior points are within the buffered mesh
        interior_points = InteriorPointGenerator.generate_interior_points(surface)
        interior_points_inside = buffered_mesh.contains(interior_points)

        return np.all(interior_points_inside)

    def find_matching_partners(self, analytical_surfaces, architectural_walls) -> dict:
        """Find matching partners between analytical surfaces and architectural walls."""
        matches = {}
        #export_surfaces_to_txt(analytical_surfaces, "all_surface_points.txt")
        for surface in analytical_surfaces:
            match_found = False
            for wall in architectural_walls:
                if self.check_surface_wall_match(surface, wall):
                    matches[surface.id] = wall.id
                    match_found = True
                    break  # Stop checking other walls once a match is found
            
            if not match_found:
                matches[surface.id] = "none"  # Use "none" to indicate no match was found
        
        return matches

def export_surfaces_to_txt(surfaces, file_path):
    """Export points from multiple surfaces to a text file for importing into Rhino."""
    with open(file_path, 'w') as f:
        for i, surface in enumerate(surfaces):
            f.write(f"# Surface {i+1}\n")
            np.savetxt(f, surface.points, delimiter=',', header="x,y,z", comments='')
            f.write("\n")  # Add a blank line between surfaces

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
    combined_mesh.export(file_path, file_type='obj')