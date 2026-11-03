package org.eclipse.imagen.media.affine;

import java.awt.geom.AffineTransform;
import java.awt.image.BufferedImage;
import org.eclipse.imagen.InterpolationNearest;
import org.eclipse.imagen.media.range.Range;

/** Checks half-open source bounds in the actual ImageN implementation. */
public class AffineScanlineRegression {
    public static void main(String[] args) {
        AffineNearestOpImage image = new AffineNearestOpImage(
                new BufferedImage(2, 2, BufferedImage.TYPE_BYTE_GRAY), null, null, null,
                new AffineTransform(), new InterpolationNearest(), new double[] {0}, true, false, null);
        check(image.performScanlineClipping(0, 0, 2, 2, 0, 0, 0, 0, 0, 4, 0, 0, 0, 0), 0, 2);
        image.incx = -1;
        image.ifracdx = 0;
        check(image.performScanlineClipping(0, 0, 2, 2, 2, 0, 0, 0, 0, 4, 0, 0, 0, 0), 1, 3);
        image.incx = 1;
        image.incy = 1;
        image.ifracdy = 0;
        check(image.performScanlineClipping(0, 0, 2, 2, -3, 0, 0, 0, 0, 8, 0, 0, 0, 0), 3, 3);
        int cases = exhaustiveNearestBounds(image);
        image.dispose();
        System.out.println("PASS: forward, reverse and empty scanline clipping; " + cases + " enumerated nearest-bound cases");
    }

    /** Independently enumerate the source position of every destination sample. */
    private static int exhaustiveNearestBounds(AffineNearestOpImage image) {
        double[] steps = {-2, -1, -.5, 0, .25, .5, 1, 2};
        int cases = 0;
        for (double dx : steps) for (double dy : steps) {
            image.incx = (int) Math.floor(dx);
            image.incy = (int) Math.floor(dy);
            image.ifracdx = (int) ((dx - image.incx) * AffineOpImage.GEOM_FRAC_MAX);
            image.ifracdy = (int) ((dy - image.incy) * AffineOpImage.GEOM_FRAC_MAX);
            for (int hx = -4; hx <= 8; hx++) for (int hy = -4; hy <= 8; hy++) {
                double sx = hx / 2.0, sy = hy / 2.0;
                int ix = (int) Math.floor(sx), iy = (int) Math.floor(sy);
                int fx = (int) ((sx - ix) * AffineOpImage.GEOM_FRAC_MAX);
                int fy = (int) ((sy - iy) * AffineOpImage.GEOM_FRAC_MAX);
                for (int start : new int[] {-3, 0, 7}) {
                    Range range = image.performScanlineClipping(0, 0, 2, 2, ix, iy, fx, fy, start, start + 8, 0, 0, 0, 0);
                    int min = range.getMin().intValue(), max = range.getMax().intValue();
                    if (min < start || max > start + 8 || max < min) {
                        throw new AssertionError("Invalid destination range: " + range);
                    }
                    for (int x = start; x < start + 8; x++) {
                        double sourceX = sx + (x - start) * dx;
                        double sourceY = sy + (x - start) * dy;
                        boolean expected = sourceX >= 0 && sourceX < 2 && sourceY >= 0 && sourceY < 2;
                        if (expected != (x >= min && x < max)) {
                            throw new AssertionError("Wrong inclusion at " + x + ": start=" + sx + "," + sy
                                    + " step=" + dx + "," + dy + " range=" + range);
                        }
                    }
                    cases++;
                }
            }
        }
        return cases;
    }

    private static void check(Range r, int min, int max) {
        if (r.getMin().intValue() != min || r.getMax().intValue() != max) {
            throw new AssertionError("Expected [" + min + "," + max + ") but got " + r);
        }
    }
}
