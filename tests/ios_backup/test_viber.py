import logging

from mvt.common.indicators import Indicators
from mvt.common.module import run_module
from mvt.ios.modules.mixed.viber import Viber

from ..utils import get_ios_backup_folder


class TestViberModule:
    def test_viber(self):
        m = Viber(target_path=get_ios_backup_folder())
        m.is_backup = True
        run_module(m)
        assert len(m.results) == 1
        assert len(m.timeline) == 1
        assert len(m.detected) == 0

    def test_detection(self, indicator_file):
        m = Viber(target_path=get_ios_backup_folder())
        m.is_backup = True
        ind = Indicators(log=logging.getLogger())
        ind.parse_stix2(indicator_file)
        # Adds a file that exists in the manifest.
        ind.ioc_collections[0]["domains"].append("kingdom-deals.com")
        m.indicators = ind
        run_module(m)
        assert len(m.detected) == 1
