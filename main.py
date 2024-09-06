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
from utils.results_analyzer import analyze_dict

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
        description="Specify the size of the buffered mesh in metres. \
            The vertices of the 3D mesh of the wall(s) are translated along the normals of each face with this value.",
    )

    grid_max_distance: float = Field(
        default=0.5,
        title="Max Spacing of Grid Points",
        description="These points, generated on the surface, test coordination with openings. \
            The max spacing controls the distance between the interior points generated."
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
    matches = SurfaceWallMatcher.find_matching_partners(analytical_surfaces, architectural_walls, function_inputs.grid_max_distance)

    # Calculate statistics
    results = analyze_dict(matches)

    if results['empty_lists']['count'] > 0:
        automate_context.attach_error_to_objects(
            category="Uncoordinated Elements",
            object_ids=results["empty_lists"]['keys'],
            message="No match found.")
        automate_context.attach_warning_to_objects(
            category='Multi-Wall Matches - Complex',
            object_ids=results["lists_greater_than_3"]['keys'],
            message="Surfaces whose points are contained in more than 3 wall objects. By definition of this algorithm possibly a dangerous analytical element. Consider refining buffer size, ETABS model or checking modelling quality in Revit."
        )
        automate_context.attach_info_to_objects(
            category="Easy Matches",
            object_ids=results["lists_with_1_item"]['keys'],
            message="Surfaces completely contained within one wall object."
        )
        automate_context.attach_info_to_objects(
            category="Easy Matches",
            object_ids=results["lists_between_2_and_3"]['keys'],
            message="Surfaces whose points are contained within two to three wall objects."
        )
        automate_context.mark_run_failed(
            "ETABS model not fully coordinated with Revit model:"
                f'\n\tNo matches: {results['empty_lists']['count']} / {len(matches)}. '
                f'\n\tEasy matches: {results['lists_with_1_item']['count']} / {len(matches)}. '
                f'\n\tMulti-wall matches (easy): {results['lists_between_2_and_3']['count']} / {len(matches)}. '
                f'\n\tMulti-wall matches (hard): {results['lists_greater_than_3']['count']} / {len(matches)}. '
        )
        automate_context.set_context_view()

    else:
        automate_context.attach_warning_to_objects(
            category='Multi-Wall Matches - Complex',
            object_ids=results["lists_greater_than_3"]['keys'],
            message="Surfaces whose points are contained in more than 3 wall objects. By definition of this algorithm possibly a dangerous analytical element. Consider refining buffer size, ETABS model or checking modelling quality in Revit."
        )
        automate_context.attach_info_to_objects(
            category="Easy Matches",
            object_ids=results["lists_with_1_item"]['keys'],
            message="Surfaces completely contained within one wall object."
        )
        automate_context.attach_info_to_objects(
            category="Easy Matches",
            object_ids=results["lists_between_2_and_3"]['keys'],
            message="Surfaces whose points are contained within two to three wall objects."
        )
        automate_context.mark_run_success(
            "ETABS model fully coordinated with Revit model."
                f'\n\tNo matches: {results['empty_lists']['count']} / {len(matches)}. '
                f'\n\tEasy matches: {results['lists_with_1_item']['count']} / {len(matches)}. '
                f'\n\tMulti-wall matches (easy): {results['lists_between_2_and_3']['count']} / {len(matches)}. '
                f'\n\tMulti-wall matches (hard): {results['lists_greater_than_3']['count']} / {len(matches)}. '
        )

if __name__ == "__main__":

    execute_automate_function(automate_function, FunctionInputs)
