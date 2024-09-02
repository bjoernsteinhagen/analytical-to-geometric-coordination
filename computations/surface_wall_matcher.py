import numpy as np
import concurrent.futures
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
    def generate_interior_points(surface, num_points=5):
        """Generate a grid of points inside the rectangular surface."""
        min_bound = np.min(surface.points, axis=0)
        max_bound = np.max(surface.points, axis=0)

        x = np.linspace(min_bound[0], max_bound[0], num_points)
        y = np.linspace(min_bound[1], max_bound[1], num_points)
        z = np.linspace(min_bound[2], max_bound[2], num_points)

        xx, yy, zz = np.meshgrid(x, y, z)
        interior_points = np.column_stack((xx.ravel(), yy.ravel(), zz.ravel()))

        return interior_points


class SurfaceWallMatcher:
    """Responsible for matching analytical surfaces with architectural walls."""

    def __init__(self, buffer_distance=0.01):
        self.buffer_distance = buffer_distance

    def check_surface_wall_match(self, surface, wall) -> bool:
        """Check if an analytical surface matches with an architectural wall."""
        buffered_mesh = MeshBufferer.create_buffered_mesh(wall.mesh, self.buffer_distance)

        vertices_inside = all(buffered_mesh.contains([point]) for point in surface.points)
        if not vertices_inside:
            return False

        interior_points = InteriorPointGenerator.generate_interior_points(surface)
        all_interior_points_inside = all(buffered_mesh.contains(interior_points))

        return all_interior_points_inside

    def find_matching_partners(self, analytical_surfaces, architectural_walls) -> dict:
        """Find matching partners between analytical surfaces and architectural walls."""
        matches = {}

        # Helper function for parallel processing
        def process_surface(surface):
            surface_bounds = surface.bounds
            match_found = False

            for wall in architectural_walls:
                if np.all(surface_bounds[0] - self.buffer_distance <= wall.bounds[1] + self.buffer_distance) and \
                   np.all(surface_bounds[1] + self.buffer_distance >= wall.bounds[0] - self.buffer_distance):
                    if self.check_surface_wall_match(surface, wall):
                        matches[surface.id] = wall.id
                        match_found = True
                        break

            if not match_found:
                matches[surface.id] = "none"

        # Use ThreadPoolExecutor for parallel processing
        with concurrent.futures.ThreadPoolExecutor() as executor:
            futures = [executor.submit(process_surface, surface) for surface in analytical_surfaces]
            concurrent.futures.wait(futures)

        return matches
