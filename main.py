"""This module contains the function's business logic.

Use the automation_context module to wrap your function in an Automate context helper.
"""
from pydantic import Field
from speckle_automate import (
    AutomateBase,
    AutomationContext,
    execute_automate_function,
)
from specklepy.objects.units import Units
from models.etabs_model import EtabsModelProcessor
from models.revit_model import RevitModelProcessor
from computations.surface_wall_matcher import SurfaceWallMatcher


class FunctionInputs(AutomateBase):
    """Author-defined function values.
    """

    revit_model_name: str = Field(
        ...,
        title="Branch name of the Revit model to check the structural model against.",
        )

    buffer_size: float = Field(
        default=0.01,
        title="Buffer size for the Revit walls (tolerance)",
        description="Specify the size of the buffered mesh. \
            The vertices of the 3D mesh of the wall(s) are translated along the normals of each face with this value.",
            json_schema_extra={"readOnly" : True,
                               },
    )

    buffer_unit: str = Field(
        default=Units.m,
        title="Buffer Unit",
        description="Unit of the buffer size value.",
        json_schema_extra={
            "examples": ["mm", "cm", "m"],
            "readOnly" : True
        },
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
    architectural_walls = revit_processor.get_architectural_walls()

    # Find matching partners
    matcher = SurfaceWallMatcher(buffer_distance=function_inputs.buffer_size)
    matches = matcher.find_matching_partners(analytical_surfaces, architectural_walls)

    print(matches)

# make sure to call the function with the executor
if __name__ == "__main__":
    # NOTE: always pass in the automate function by its reference; do not invoke it!

    # Pass in the function reference with the inputs schema to the executor.
    execute_automate_function(automate_function, FunctionInputs)
