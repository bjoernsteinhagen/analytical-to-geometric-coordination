import numpy as np
from speckle_automate import AutomationContext


class AnalyticalSurface:
    """Represents analytical surfaces extracted from the ETABS model."""
    def __init__(self, points, surface_id):
        self.points = np.array(points)
        self.id = surface_id
        self.bounds = np.array([np.min(points, axis=0), np.max(points, axis=0)])


class EtabsModelProcessor:
    """Handles ETABS model validation and the extraction of analytical surfaces."""
    def __init__(self, automate_context: AutomationContext):
        self.etabs_commit = automate_context.receive_version()

    def validate_source(self):
        """Validate the ETABS source model."""
        try:
            model_element = self.etabs_commit["@Model"]
            if model_element is None:
                return False
            if getattr(model_element, "speckle_type", None) != "Objects.Structural.Analysis.Model":
                return False
        except KeyError:
            return False
        return True

    def extract_analytical_surfaces(self):
        """Extract analytical surfaces from the ETABS model."""
        elements = getattr(self.etabs_commit["@Model"], "elements", [])
        application_ids = set()
        analytical_surfaces = [
            self.create_analytical_surface(element)
            for element in elements
            if "Element2D" in element.speckle_type
            and element.applicationId not in application_ids
            and not application_ids.add(element.applicationId)
        ]
        return analytical_surfaces

    @staticmethod
    def create_analytical_surface(surface) -> AnalyticalSurface:
        """Create an AnalyticalSurface object from an element."""
        vertices_array = np.array(surface.displayValue[0].vertices).reshape(-1, 3)
        return AnalyticalSurface(vertices_array, surface.id)

    def process(self):
        """Validate and extract analytical surfaces from the ETABS model."""
        if self.validate_source():
            return self.extract_analytical_surfaces()
        raise ValueError("Invalid ETABS model source.")
