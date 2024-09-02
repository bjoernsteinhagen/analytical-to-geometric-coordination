# Speckle Automate Function: ETABS Analytical Surfaces to Revit Walls Coordination
## 🌐 Overview
This analytical-to-geometric-coordination function in Speckle Automate is a specialized tool designed for structural engineers and architects to ensure accurate coordination between analytical models and architectural designs. It bridges the gap between ETABS finite element analysis models and architectural Revit models, enabling rapid assessment of coordination between 2d planar analytical surfaces in ETABS and the volumetric walls in the Revit architectural model.

## ⚠️ Disclaimer: Conceptual Demonstration Only
**IMPORTANT:** This function is a conceptual demonstration and is not intended for production use. It illustrates how Speckle Automate can facilitate the alignment of structural and architectural models, reducing the risk of miscommunication and errors in structural behavior and design.

## 🔍 Functionality
Coordination between analytical and architectural models is crucial for accurate structural analysis and design in construction and engineering. Misalignment between these models can lead to incorrect results and communication issues. This function demonstrates Speckle's ability to integrate and coordinate data from different models, ensuring that analytical surfaces and architectural walls are aligned.

## ⚙️ How It Works

The function to check the coordination between ETABS analytical surfaces and Revit architectural walls involves several key components and steps:

1. **Creating a Buffered Mesh**:
   - **Function**: `MeshBufferer.create_buffered_mesh`
   - **Overview**: The function creates a buffered version of each architectural wall mesh to account for slight mismatches and ensure robust matching. This is achieved by moving each vertex along its normal by a specified `buffer_distance`. The buffered mesh then checks if the analytical surfaces fall within this expanded volume.

     ```python
     buffered_mesh = MeshBufferer.create_buffered_mesh(wall.mesh, self.buffer_distance)
     ```

   - **Mathematical Detail**: The new vertex positions are calculated as `new_vertex = vertex + buffer_distance * normal`, where `normal` is the vertex normal vector.

2. **Generating Interior Points**:
   - **Function**: `InteriorPointGenerator.generate_interior_points`
   - **Overview**: A grid of interior points is generated for a given analytical surface. This grid spans the bounds of the surface and helps verify if the surface is completely within the buffered wall mesh.

     ```python
     interior_points = InteriorPointGenerator.generate_interior_points(surface)
     ```

   - **Mathematical Detail**: The function creates a 3D grid of points within the bounding box of the surface using `np.meshgrid` to generate combinations of `x`, `y`, and `z` coordinates.

3. **Checking Surface-Wall Match**:
   - **Function**: `SurfaceWallMatcher.check_surface_wall_match`
   - **Overview**: This function performs a detailed check to determine if the analytical surface matches with a given architectural wall. It first verifies if all vertices of the surface are contained within the buffered wall mesh. It then checks if all generated interior points of the surface are also inside the buffered wall mesh.

     ```python
     vertices_inside = all(buffered_mesh.contains([point]) for point in surface.points)
     all_interior_points_inside = all(buffered_mesh.contains(interior_points))
     ```

   - **Mathematical Detail**: The containment check verifies if each point `p` of the surface lies inside the buffered mesh volume. This involves a point-in-mesh test, which is typically a geometric inclusion test.

4. **Finding Matching Partners**:
   - **Function**: `SurfaceWallMatcher.find_matching_partners`
   - **Overview**: This function iterates through all analytical surfaces and architectural walls, checking for matches. It uses bounding box overlap as a preliminary filter (considering the buffer distance) before performing detailed matching checks. It returns a dictionary mapping surface IDs to wall IDs if a match is found or "none" if no match is found.

     ```python
     if np.all(surface.bounds[0] - self.buffer_distance <= wall.bounds[1] + self.buffer_distance) and \
        np.all(surface.bounds[1] + self.buffer_distance >= wall.bounds[0] - self.buffer_distance):
         if self.check_surface_wall_match(surface, wall):
             matches[surface.id] = wall.id
             match_found = True
             break
     ```

   - **Mathematical Detail**: The bounding box overlap is verified by checking if the surface's expanded bounding box intersects with the wall mesh's expanded bounding box, using the buffer distance to account for minor inaccuracies.

By following these steps, the function enables structural engineers to effectively coordinate analytical surfaces from ETABS models with architectural walls from Revit models, ensuring alignment and accuracy in the structural design process.

## 🛠️ Potential Use Cases
* **Structural-Architectural Coordination:** Ensures that analytical models align correctly with architectural designs, preventing structural miscalculations.
* **Design Validation:** Allows engineers to verify that the analytical model accurately reflects the architectural intent, reducing the risk of design errors.
* **Communication Improvement:** Enhances communication between structural engineers and architects by clearly validating model alignment.

## 🚀 Getting Started and Contributing
Refer to our Docs: https://speckle.guide/automate/

## 📧 Contact
For more information or to provide feedback, please refer to our [Community Forum](https://speckle.community/).
