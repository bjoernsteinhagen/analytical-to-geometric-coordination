import numpy as np

class SurfaceWallMatcher:
    """Handles the matching of analytical surfaces to architectural walls based on spatial proximity and containment logic."""

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

    @staticmethod
    def is_surface_coordinated(surface: 'AnalyticalSurface', candidate_walls: list['RevitWall']) -> list[str]:
        """
        Checks if a surface is coordinated with any walls in the list of candidate walls.
        
        Args:
            surface (AnalyticalSurface): The surface to check.
            candidate_walls (list[RevitWall]): List of walls to check against.

        Returns:
            list[str]: List of wall IDs that the surface is coordinated with.
        """
        matching_wall_ids = []

        # Combine vertices and interior points for the check
        surface.generate_interior_points()
        all_points = np.vstack((surface.points, surface.interior_points))

        for wall in candidate_walls:
            # Check if all points are within this wall's mesh
            points_contained = wall.buffered_mesh.contains(all_points)

            if points_contained.all():
                # If all points are within this wall's mesh, add wall id to matches and break
                matching_wall_ids.append(wall.id)
                break
            else:
                # If not all points are within this wall's mesh, filter out points that are contained
                remaining_points = all_points[~points_contained]

                if remaining_points.size == 0:
                    # If no remaining points, all points were contained
                    matching_wall_ids.append(wall.id)
                    break  # All points are accounted for, so we can stop searching

                # If some points are contained, remember this wall and continue
                if remaining_points.size < all_points.shape[0]:
                    matching_wall_ids.append(wall.id)

        return matching_wall_ids


    @staticmethod
    def find_matching_partners(surfaces: list['AnalyticalSurface'], walls: list['RevitWall']) -> dict:
        """
        Finds and matches analytical surfaces to architectural walls.

        Args:
            surfaces (list[AnalyticalSurface]): The list of analytical surfaces to check.
            walls (list[RevitWall]): The list of walls to match against.

        Returns:
            dict: Mapping of surface IDs to the wall IDs they are coordinated with.
        """
        matches = {}

        for surface in surfaces:
            # Step 1: Filter the candidate walls based on spatial proximity
            candidate_walls = SurfaceWallMatcher.spatial_proximity_filter(surface, walls)
            
            # Step 2: Check if the surface is coordinated with any candidate walls
            matching_wall_ids = SurfaceWallMatcher.is_surface_coordinated(surface, candidate_walls)

            # Step 3: If there are matching walls, store them in the matches dictionary
            if matching_wall_ids:
                matches[surface.id] = matching_wall_ids

        return matches
