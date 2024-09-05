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

    def generate_interior_points(self, num_points=4):
        """
        Generate a series of interior points on the surface for additional checks.
        
        Args:
            num_points (int): Number of interior points to generate.

        Returns:
            np.ndarray: Array of interior points inside the surface.
        """
        # Compute the centroid of the surface
        centroid = np.mean(self.points, axis=0)

        # Use centroid as a base and perturb it slightly to create interior points
        interior_points = [centroid + (np.random.rand(3) - 0.5) * 0.01 for _ in range(num_points)]
        self.interior_points = interior_points


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

def export_surfaces_to_txt(surfaces, file_path):
    """Export points from multiple surfaces to a text file for importing into Rhino."""
    with open(file_path, 'w') as f:
        for i, surface in enumerate(surfaces):
            f.write(f"# Surface {i+1}\n")
            np.savetxt(f, surface.points, delimiter=',', header="x,y,z", comments='')
            f.write("\n")  # Add a blank line between surfaces