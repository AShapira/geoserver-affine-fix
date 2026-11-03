import unittest
import tempfile
from pathlib import Path
import numpy as np
import rasterio
from rasterio.enums import ColorInterp
from unittest.mock import patch
from affine_fix.typed_suite import samples, style, fixtures


class TypedOracleTests(unittest.TestCase):
    def test_written_rgba_tiff_retains_alpha_metadata(self):
        with tempfile.TemporaryDirectory() as folder, patch('affine_fix.typed_suite.SIZE', 32):
            entries=fixtures(Path(folder)/'fixtures', ('rgba',))
            for entry in entries:
                with rasterio.open(entry['path']) as ds:
                    self.assertEqual(ds.colorinterp[-1],ColorInterp.alpha)
                    self.assertEqual(ds.count,4)
    def test_rgb_channels_and_multispectral_selection(self):
        x=np.array([256]);y=np.array([256])
        rgb,expected=samples('rgb',x,y)
        np.testing.assert_array_equal(rgb[:,0],[160,40,80])
        data,display=samples('multispectral',x,y)
        self.assertEqual(data.dtype,np.uint16)
        np.testing.assert_array_equal(data[[3,1,0],0]//257,rgb[:,0])
        self.assertEqual(int(data[2,0]),17*257)
        np.testing.assert_array_equal(expected,display)

    def test_alpha_and_nodata_are_distinct_from_valid_zero_elevation(self):
        x=np.array([1024,1400,128]);y=np.array([1024,600,256])
        data,expected=samples('rgba',x,y)
        np.testing.assert_array_equal(data[3],[0,128,255])
        for kind in ('dem','dem_nan'):
            data,expected=samples(kind,x,y)
            self.assertEqual(int(expected[0,3]),0)
            self.assertEqual(float(data[0,2]),0)
            self.assertEqual(int(expected[2,3]),255)
            if kind=='dem_nan':self.assertTrue(np.isnan(data[0,0]))
            else:self.assertEqual(float(data[0,0]),-9999)

    def test_multispectral_style_has_explicit_range_and_band_order(self):
        s=style('multispectral')
        self.assertLess(s.index('<SourceChannelName>4'),s.index('<SourceChannelName>2'))
        self.assertIn('65535',s)
        self.assertIn('StretchToMinimumMaximum',s)


if __name__=='__main__':unittest.main()
