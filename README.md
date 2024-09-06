# 📐 Analytical to Geometric Coordination

This [Automate function](https://automate.speckle.dev/) enables the coordination of walls between ETABS and Revit. The primary goal is to ensure that analytical models accurately represent and align with the corresponding geometric elements in architectural models. In a nutshell, the surfaces of an ETABS model are checked against spatial relatable 'counterparts' in the Revit model.

## ⚠️ Disclaimer
Conceptual Demonstration Only

## 🧩 How Matches are Found

The matching process in this project coordinates **2D analytical surfaces** from ETABS with **3D Revit wall meshes**. Here's a breakdown of how the matches are computed:

### 1. **Buffered Mesh Creation**
A **buffered version** of each Revit wall mesh is created by expanding it outward. This helps account for small mismatches between analytical surfaces and walls. Walls must be coordinated, however, an exact 1-to-1 is seen as unrealistic. This enables some degree of freedom when defining the FEM model, making sensible simplifications and assumption. Overlap between Revit wall and floor joins can also be compensated for here. The function moves vertices along their normal by a specified `buffer_distance`.

<figure style="display: flex; align-items: center; gap: 20px;">
  <img width="459" alt="image" src="https://github.com/user-attachments/assets/0ea98650-0113-4007-b358-1943076c84a8">
</figure>


### 2. **Generating Interior Points**
A grid of points is generated inside each analytical surface's bounding box. These points help determine whether the surface is fully contained within the buffered mesh of a wall.

### 3. **Checking Surface-Wall Match**
Each analytical surface is compared against the buffered meshes. A surface may be contained in more than one wall mesh (consider adjoining walls). Therefore, all of the `candidate_walls` are investigated. `candidate_walls` is the result of `spatial_proximity_filter` (see below). The aim of the `spatial_proximity_filter` is minimise computational time. For each `surface`, the collection of points (defining `vertices` and generated grid of `interior_points`) are tested for a counterpart wall containing the point(s).
* 😊 **Easy matches** - all points of a surface are accounted for within a single Revit wall. 
* 😌 **Multi-wall matches (easy)** - all points of a surface are accounted for within two or three Revit walls.
* 😅 **Multi-wall matches (hard)** - all points of a surface are accounted for, however, more than three counterparts have been identified. This is marked as a warning and can mean many things, but not necessarily an error. Either the `buffer_distance` is too high and walls above and below are being found, modelling quality in Revit is poor and there are a lot of overlapping elements or the analytical surfaces are too big in which a refinement of the elements is recommended.
* 🤷‍♂️ **No matches** - if none of the points or some of the points of a surface are not accounted for, this would result in failure. The use of `interior_points` account for openings (e.g. walls or doors). Below is an example of a none match since the `interior_points` over the opening will not be accounted for.
  
  <img width="512" alt="image" src="https://github.com/user-attachments/assets/eb89b9a4-d8d1-4184-8d8e-091f6483400f">


### 4. **Finding Matching Partners**
The process iterates through all surfaces and walls, using a preliminary bounding box filter to narrow down potential matches. For each candidate, the detailed vertex and interior point check is performed. The result is a dictionary mapping analytical surface IDs to wall IDs or "none" if no match is found.


## ⚙️ Assumptions and Limitations

### Assumptions

#### Coordinate System Alignment:
The analytical surfaces and architectural walls are assumed to be in the same global coordinate system. Any discrepancies in coordinate systems between the models must be resolved before running the analysis.

#### Geometry Accuracy:
The input models are assumed to accurately represent their real-world counterparts. Surfaces and walls should be free from significant errors, such as incorrect scaling or misaligned geometry. Presumed units of the Revit model is m. Scaling of the ETABS model is implemented to go from mm and cm to m should the model be defined in those units.

#### Wall and Surface Representation:
The 3D meshes of the Revit walls are used in the analysis, while analytical surfaces from ETABS are treated as 2D planar geometries. The function assumes that walls are composed of valid, watertight meshes and surfaces are well-defined with no self-intersections. The 3D meshes of the Revit walls include information regarding openings and as such provide a good basis for mesh containing functions. The project includes functionality to filter out only the information that is needed (i.e. Walls). In Revit this is done by accessing the appropriate collections, while in ETABS the surfaces are filtered and the flat plate elements (floors) are ignored.

For the Revit walls, that is done by accessing the `name` attribute of `collections`:

```python
def get_architectural_walls(self, buffer_distance) -> List[RevitWall]:

    if not hasattr(self.revit_model, "elements"):
        raise AttributeError("The provided Revit model has no 'elements' attribute.")

    collections = self.revit_model.elements
    architectural_walls = []

    if not any(collection.name == 'Walls' for collection in collections):
        raise ValueError("None of the collections have 'Walls' as a named attribute.")
```

For ETABS, the model needs to go through a series of checks:
* Is the commit coming from ETABS?
```python
 def process(self):
     """Validate and extract analytical surfaces from the ETABS model."""
     if self.validate_source():
         return self.extract_analytical_surfaces()
     raise ValueError("Invalid ETABS model source.")
```
* Extract the `CSIElement2D` and ignore the rest. The `create_analytical_surface()` only creates walls and ignores floors by inspecting at the variance in the Z coordinates. This is in the `_is_floor()` function.
```python
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
```

#### Proximity Filtering:
The spatial proximity filter assumes that architectural walls and analytical surfaces that are close to each other geometrically should be considered for further coordination checks. The distance threshold used in the filter is assumed to be appropriate for the project scale. The global Z coordinates are used in this instance to filter out walls above or below the surface(s) in question. There is no AABB (Axis-Aligned Bounding Box) reliance for filtering which slightly compromises computational speed, but allows accurate checking of walls that are not aligned with a global X- or Y-axis.

 ```python
 @staticmethod
 def spatial_proximity_filter(surface: 'AnalyticalSurface', walls: list['RevitWall']) -> list['RevitWall']:
     """
     Filters out walls that are too high or low based on the z-coordinates of the surface.

     Args:
         surface (AnalyticalSurface): The analytical surface to check.
         walls (list[RevitWall]): The list of walls to filter.

     Returns:
         list[RevitWall]: Filtered list of candidate walls for further inspection.
     """
     filtered_walls = []
     surface_min_z, surface_max_z = surface.bounds[0][2], surface.bounds[1][2]

     for wall in walls:
         wall_min_z, wall_max_z = wall.buffered_mesh.bounds[0][2], wall.buffered_mesh.bounds[1][2]

         # Check if the wall is within the z range of the surface
         if not (surface_max_z < wall_min_z or surface_min_z > wall_max_z):
             filtered_walls.append(wall)

     return filtered_walls
```

### Limitations

#### Complex Geometries:
The tool may not perform well with highly complex or irregular wall geometries, especially if the geometry is not sufficiently simplified or represented by a clean mesh. Surfaces with non-planar shapes or highly fragmented wall meshes may lead to false positives or negatives in the coordination check.

#### Tolerance Sensitivity:
The proximity filter and coordination checks are highly sensitive to the distance threshold and tolerances set in the process. If the thresholds are not carefully tuned to the project needs, some valid matches may be excluded or false matches may be included. The buffered mesh distance should be coordinated with the modelling standards for the project (i.e. are Revit walls attached to the bottom of slab soffits etc.).

#### 2D Surface Approximation:
Since analytical surfaces are treated as 2D planes, some nuances of the real-world 3D structure, like small deviations in surface thickness or curvature, may not be captured, which could affect the accuracy of the coordination check. All surfaces are assumed to be defined by four vertices.

#### Performance on Large Datasets:
For very large datasets, the spatial indexing and matching process may experience performance degradation. The tool relies on spatial indexing for efficiency, but this approach may not scale perfectly with extremely large or dense models.

#### Handling Overlapping Walls:
The current logic assumes that walls do not significantly overlap in the 3D model. Overlapping walls might cause errors in the proximity filter and the surface coordination check, leading to inaccurate results.

#### Non-Standard Architectural Elements:
The tool is optimized for standard architectural wall geometries. Non-standard elements like curved walls, sloped surfaces, or non-rectilinear shapes may not be correctly identified or coordinated with the analytical surfaces.

## 📜 Functions

### `find_matching_partners()`
**Description:**  
This function is designed to find matches between analytical surfaces and architectural walls. It uses spatial indexing to efficiently identify which surfaces are associated with which walls based on spatial proximity and alignment criteria.

**Assumptions:**
- Analytical surfaces and architectural walls are represented as 3D geometries.
- The spatial indexing mechanism is used to handle large datasets efficiently.

**Theory:**  
The function relies on spatial indexing and proximity algorithms to match surfaces and walls. It calculates spatial relationships and filters matches based on predefined criteria.

**Methodology:**
1. Index all architectural walls.
2. For each analytical surface, query the spatial index to find potential matches.
3. Validate and refine matches based on geometric alignment and boundary conditions.

### `spatial_proximity_filter()`
**Description:**  
This function filters potential matches based on spatial proximity. It ensures that only those pairs of surfaces and walls that are within a specified distance threshold are considered for further evaluation.

**Assumptions:**
- The distance threshold is defined based on the scale and precision requirements of the project.
- The function assumes that surfaces and walls are within the same coordinate system.

**Theory:**  
By applying a distance filter, the function reduces the number of potential matches to those that are likely relevant, improving the efficiency of subsequent matching processes.

**Methodology:**
1. Define a distance threshold.
2. For each pair of potential matches, calculate the distance between them.
3. Keep only those pairs where the distance is below the threshold.

### `is_surface_coordinated()`
**Description:**  
This function checks whether an analytical surface is coordinated with a given architectural wall. It verifies if the surface lies entirely within the wall's geometry or if its edges align with the wall's faces.

**Assumptions:**
- The function assumes accurate representation of both surfaces and walls in 3D space.
- It operates under the assumption that the surfaces and walls are well-defined and accurately modeled.

**Theory:**  
The function uses geometric calculations to determine if a surface is fully contained within or aligns with the wall. This involves checking geometric intersections and alignments.

**Methodology:**
1. Check if the surface's points lie within the wall's geometry.
2. Verify if the surface's edges align with the wall's faces.
3. Return a boolean result indicating whether the surface is coordinated with the wall.

## 📚 Getting Started / Contributing
Refer to the [Automate Docs](https://speckle.guide/automate/).


