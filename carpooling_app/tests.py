from django.test import TestCase
from django.conf import settings
from .utils import get_road_distance_osrm

class OSRMUtilsTestCase(TestCase):
    def test_get_road_distance_osrm_valid_coordinates(self):
        """
        Test OSRM distance calculation between two known points.
        Example: Surat Railway Station -> Surat Airport
        """
        # Surat Castle
        lat1, lon1 =21.196783453087143, 72.81770132423027

        # VNSGU
        lat2, lon2 = 21.153603168257987, 72.78320242757216

        distance = get_road_distance_osrm(lat1, lon1, lat2, lon2)
        print("OSRM Distance:", distance)

        self.assertIsNotNone(distance, "OSRM distance should not be None")
        self.assertGreater(distance, 0, "Distance should be greater than 0")

    def test_get_road_distance_osrm_invalid_coordinates(self):
        """
        Test OSRM should return None or fail gracefully with invalid coordinates.
        """
        distance = get_road_distance_osrm(0, 0, 0, 0)
        print("Invalid coordinate distance:", distance)

        # It might return None or a valid value if OSRM defaults, so we just check type
        self.assertTrue(distance is None or isinstance(distance, float))

    def test_get_road_distance_osrm_reverse_coordinates(self):
        """
        Test with reversed coordinates to ensure function handles both directions.
        """
        # # Surat Castle to VNSGU
        lat1, lon1 = 21.153603168257987, 72.78320242757216
        lat2, lon2 = 21.196783453087143, 72.81770132423027

        distance = get_road_distance_osrm(lat1, lon1, lat2, lon2)
        print("Reverse OSRM Distance:", distance)

        self.assertIsNotNone(distance)
        self.assertGreater(distance, 0)
