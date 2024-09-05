"""This module contains the function's business logic.

Use the automation_context module to wrap your function in an Automate context helper.
"""
from enum import Enum
from pydantic import Field
from speckle_automate import (
    AutomateBase,
    AutomationContext,
    execute_automate_function,
)
from models.etabs_model import EtabsModelProcessor
from models.revit_model import RevitModelProcessor
from computations.surface_to_wall_matcher import SurfaceWallMatcher

class Units(Enum):
    Metre = "m"
    Centimetre = "cm"
    Millimetre = "mm"

class FunctionInputs(AutomateBase):
    """Author-defined function values.
    """

    revit_model_name: str = Field(
        ...,
        title="Branch name of the Revit model to check the structural model against.",
        )

    buffer_size: float = Field(
        default=0.01,
        title="Buffer Size",
        description="Specify the size of the buffered mesh. \
            The vertices of the 3D mesh of the wall(s) are translated along the normals of each face with this value.",
    )

    buffer_unit: Units = Field(
        default=Units.Metre,
        title="Buffer Unit",
        description="Unit of the buffer size value.",
    )

def automate_function(
    automate_context: AutomationContext,
    function_inputs: FunctionInputs,
) -> None:
    """This is the Speckle Automate function.

    Args:
        automate_context: A context-helper object that carries relevant information
            about the runtime context of this function.
            It gives access to the Speckle project data that triggered this run.
            It also has convenient methods for attaching result data to the Speckle model.
        function_inputs: An instance object matching the defined schema.
    """
    # Process ETABS model
    etabs_processor = EtabsModelProcessor(automate_context)
    analytical_surfaces = etabs_processor.process()

    # Process Revit model
    revit_model = RevitModelProcessor.get_model(
        automate_context.speckle_client,
        automate_context.automation_run_data.project_id,
        function_inputs.revit_model_name
    )
    revit_processor = RevitModelProcessor(revit_model)
    architectural_walls = revit_processor.get_architectural_walls(function_inputs.buffer_size)

    # Find matching partners
    matches = SurfaceWallMatcher.find_matching_partners(analytical_surfaces, architectural_walls)

    # Report
    number_of_surfaces = len(analytical_surfaces)
    none_ids = [surface_id for surface_id, wall_ids in matches.items() if not wall_ids]
    none_count = len(none_ids)
    
    # Calculate statistics
    easy_match = 0
    tricky_matches = 0
    hazardous_matches = 0
    
    for wall_ids in matches.values():
        if not wall_ids:  # Skip if no walls matched
            continue
        
        num_matches = len(wall_ids)
        if num_matches == 1:
            easy_match += 1
        elif 2 <= num_matches <= 3:
            tricky_matches += 1
        elif num_matches > 3:
            hazardous_matches += 1

    if none_count > 0:
        automate_context.attach_error_to_objects(
            category="Uncoordinated analytical surfaces",
            object_ids=none_ids,
            message="These surfaces have either extents outside of the scope of the buffered mesh or cannot be associated with a wall object entirely.")
        automate_context.mark_run_failed(
            "ETABS model not fully coordinated with Revit model:"
                f'\n\tNone Count: {none_count} / {number_of_surfaces}. '
                f'\n\tEasy Matches: {easy_match} / {number_of_surfaces}. '
                f'\n\tTricky Matches: {tricky_matches} / {number_of_surfaces}. '
                f'\n\tHazardous Matches: {hazardous_matches} / {number_of_surfaces}. '
        )
        automate_context.set_context_view()

    else:
        automate_context.mark_run_success(
            "ETABS model fully coordinated with Revit model."
                f'\n\tNone Count: {none_count} / {number_of_surfaces}. '
                f'\n\tEasy Matches: {easy_match} / {number_of_surfaces}. '
                f'\n\tTricky Matches: {tricky_matches} / {number_of_surfaces}. '
                f'\n\tHazardous Matches: {hazardous_matches} / {number_of_surfaces}.'
        )

# make sure to call the function with the executor
if __name__ == "__main__":
    # NOTE: always pass in the automate function by its reference; do not invoke it!

    # Pass in the function reference with the inputs schema to the executor.
    execute_automate_function(automate_function, FunctionInputs)
