import numpy as np
from speckle_automate import AutomationContext
from utils.unit_converter import convert_units


class AnalyticalSurface:
    """Represents analytical surfaces extracted from the ETABS model."""
    def __init__(self, points, surface_id):
        self.points = np.array(points)
        self.id = surface_id
        self.bounds = np.array([np.min(points, axis=0), np.max(points, axis=0)])
        self.interior_points = None

    def generate_grid(self, max_distance = 0.5):
        """
        Generate a grid of points on the surface based on the maximum distance between points.

        Args:
            max_distance (float): Maximum distance between grid points.

        Returns:
            np.ndarray: Array of grid points on the surface in 3D space.
        """
        # Step 1: Define the local 2D coordinate system
        v0, v1, v2, v3 = self.points

        # Create vectors representing the sides of the surface
        u_vec = v1 - v0  # Vector along one side
        v_vec = v3 - v0  # Vector along the other side

        # Normalize the vectors
        u_vec = u_vec / np.linalg.norm(u_vec)
        v_vec = v_vec / np.linalg.norm(v_vec)

        # Step 2: Project vertices onto the local 2D plane (aligned to the surface)
        # We will use (v0, u_vec, v_vec) as the base for a local coordinate system
        def project_to_local_2d(point):
            relative_point = point - v0
            u_coord = np.dot(relative_point, u_vec)
            v_coord = np.dot(relative_point, v_vec)
            return np.array([u_coord, v_coord])

        # Project all 4 vertices to the local 2D system
        v0_2d = np.array([0, 0])
        v1_2d = project_to_local_2d(v1)
        v2_2d = project_to_local_2d(v2)
        v3_2d = project_to_local_2d(v3)

        # Step 3: Generate the grid in 2D space
        # Get the bounding box in 2D space
        min_x = min(v0_2d[0], v1_2d[0], v2_2d[0], v3_2d[0])
        max_x = max(v0_2d[0], v1_2d[0], v2_2d[0], v3_2d[0])
        min_y = min(v0_2d[1], v1_2d[1], v2_2d[1], v3_2d[1])
        max_y = max(v0_2d[1], v1_2d[1], v2_2d[1], v3_2d[1])

        # Create a grid of points within the bounding box
        x_coords = np.arange(min_x, max_x, max_distance)
        y_coords = np.arange(min_y, max_y, max_distance)
        grid_2d = np.array([[x, y] for x in x_coords for y in y_coords])

        # Step 4: Transform the grid back to 3D space
        def transform_to_3d(point_2d):
            return v0 + point_2d[0] * u_vec + point_2d[1] * v_vec

        grid_3d = np.array([transform_to_3d(p) for p in grid_2d])

        # Step 5: Filter the points that are inside the quadrilateral (in 3D space)
        def is_point_in_surface(point):
            # Use barycentric coordinates to check if point is inside the quadrilateral
            # Triangulate the quadrilateral into two triangles (v0, v1, v2) and (v0, v2, v3)
            def point_in_triangle(pt, tri):
                v0, v1, v2 = tri
                u = v1 - v0
                v = v2 - v0
                w = pt - v0

                u_dot_u = np.dot(u, u)
                u_dot_v = np.dot(u, v)
                u_dot_w = np.dot(u, w)
                v_dot_v = np.dot(v, v)
                v_dot_w = np.dot(v, w)

                denom = u_dot_u * v_dot_v - u_dot_v * u_dot_v
                s_numer = u_dot_u * v_dot_w - u_dot_v * u_dot_w
                t_numer = v_dot_v * u_dot_w - u_dot_v * v_dot_w

                s = s_numer / denom
                t = t_numer / denom

                return (s >= 0) and (t >= 0) and (s + t <= 1)

            # Check both triangles
            return point_in_triangle(point, [v0, v1, v2]) or point_in_triangle(point, [v0, v2, v3])

        # Filter grid points to only include those inside the surface
        self.interior_points = np.array([p for p in grid_3d if is_point_in_surface(p)])


class EtabsModelProcessor:
    """Handles ETABS model validation and the extraction of analytical surfaces."""
    def __init__(self, automate_context: AutomationContext):
        self.etabs_commit = automate_context.receive_version()
        self.units = None

    def validate_source(self):
        """Validate the ETABS source model."""
        try:
            model_element = self.etabs_commit["@Model"]
            if model_element is None:
                return False
            if getattr(model_element, "speckle_type", None) != "Objects.Structural.Analysis.Model":
                return False
            self.units = self.get_model_units(model_element)
        except KeyError:
            return False
        return True

    def get_model_units(self, model_element):
        """Extract and return the units of the model."""
        try:
            return model_element.specs.settings.modelUnits.length
        except AttributeError as exc:
            raise AttributeError("Units of the ETABS model cannot be found. Please ensure the model contains valid unit information in the 'modelUnits' attribute.") from exc

    def extract_analytical_surfaces(self):
        """Extract analytical surfaces from the ETABS model."""
        elements = getattr(self.etabs_commit["@Model"], "elements", [])
        application_ids = set()
        analytical_surfaces = [
            surface
            for element in elements
            if "Element2D" in element.speckle_type
            and element.applicationId not in application_ids
            and not application_ids.add(element.applicationId)
            and (surface := self.create_analytical_surface(element)) is not None
        ]

        return analytical_surfaces

    def create_analytical_surface(self, surface) -> AnalyticalSurface:
        """Create an AnalyticalSurface object from an element."""
        vertices_array = np.array(surface.displayValue[0].vertices).reshape(-1, 3)

        # Check if the surface is a floor and skip it if so
        if self._is_floor(vertices_array):
            return None  # Skip this surface

        # Only apply scaling if units are not 'm'
        if self.units in ['mm', 'cm']:
            # Apply scaling function element-wise for each coordinate
            scaling_factors = np.vectorize(lambda x: convert_units(x, self.units))
            scaled_vertices_array = scaling_factors(vertices_array)
        else:
            scaled_vertices_array = vertices_array  # No scaling needed

        return AnalyticalSurface(scaled_vertices_array, surface.id)

    @staticmethod
    def _is_floor(vertices, tolerance=1e-5):
        """Check if the z-coordinates of the vertices are approximately the same."""
        z_coords = vertices[:, 2]
        return np.ptp(z_coords) < tolerance

    def process(self):
        """Validate and extract analytical surfaces from the ETABS model."""
        if self.validate_source():
            return self.extract_analytical_surfaces()
        raise ValueError("Invalid ETABS model source.")
