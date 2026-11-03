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
        checkMaskOutsideIsZero();
        // A sample 1e-6 source pixels inside the boundary must not drift outside
        // after 202 scanline increments (regression for 20-bit fraction rounding).
        image.incx = 0;
        image.ifracdx = 0;
        double dy = -0.004665345964671403;
        double sy = 1e-6 - 202 * dy;
        image.incy = -1;
        image.ifracdy = (int) Math.round((dy + 1) * AffineOpImage.GEOM_FRAC_MAX);
        int fy = (int) Math.floor(sy * AffineOpImage.GEOM_FRAC_MAX);
        check(image.performScanlineClipping(0, 0, 2, 2, 0, 0, 0, fy, 0, 256, 0, 0, 0, 0), 0, 203);
        // Integer step times the fraction denominator must be widened before multiplication.
        image.incx = 16;
        image.incy = 0;
        image.ifracdy = 0;
        check(image.performScanlineClipping(0, 0, 32, 2, 0, 0, 0, 0, 0, 4, 0, 0, 0, 0), 0, 2);
        image.dispose();
        BufferedImage edgeSource = new BufferedImage(2048, 2, BufferedImage.TYPE_BYTE_GRAY);
        edgeSource.getRaster().setSample(2047, 0, 0, 173);
        AffineNearestOpImage edge = new AffineNearestOpImage(edgeSource, org.eclipse.imagen.BorderExtender.createInstance(org.eclipse.imagen.BorderExtender.BORDER_ZERO), null, null,
                AffineTransform.getTranslateInstance(0.5 - 2047.999964, 0),
                new InterpolationNearest(), new double[] {0}, true, false, null);
        int value = edge.getData(new java.awt.Rectangle(0, 0, 1, 1)).getSample(0, 0, 0);
        edge.dispose();
        // Nonzero shear selects Affine rather than the separate Scale shortcut.
        org.eclipse.imagen.RenderedOp maskEdge = AffineDescriptor.create(edgeSource,
                new AffineTransform(1, 0, .01, 1, 0.5 - 2047.999964 - .005, 0), new InterpolationNearest(),
                new double[] {0}, new org.eclipse.imagen.ROI(edgeSource, 1), false, true, null,
                new java.awt.RenderingHints(org.eclipse.imagen.ImageN.KEY_BORDER_EXTENDER,
                        org.eclipse.imagen.BorderExtender.createInstance(org.eclipse.imagen.BorderExtender.BORDER_ZERO)));
        boolean maskIncluded = ((org.eclipse.imagen.ROI) maskEdge.getProperty("ROI")).contains(0, 0);
        maskEdge.dispose();
        if (!maskIncluded) throw new AssertionError("Float-narrowed binary mask lost source edge");
        if (value != 173) throw new AssertionError("Float-narrowed source edge lost: " + value);
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

    /** A transformed binary mask must not repeat the last in-bounds sample. */
    private static void checkMaskOutsideIsZero() {
        BufferedImage source = new BufferedImage(4, 4, BufferedImage.TYPE_BYTE_GRAY);
        for (int y = 0; y < 4; y++) for (int x = 0; x < 4; x++) source.getRaster().setSample(x, y, 0, 255);
        org.eclipse.imagen.ROI mask = new org.eclipse.imagen.ROI(source, 1);
        AffineTransform tx = new AffineTransform();
        tx.translate(45, 5);
        tx.rotate(Math.PI / 6);
        tx.scale(20, 20);
        java.awt.RenderingHints hints = new java.awt.RenderingHints(org.eclipse.imagen.ImageN.KEY_BORDER_EXTENDER,
                org.eclipse.imagen.BorderExtender.createInstance(org.eclipse.imagen.BorderExtender.BORDER_COPY));
        org.eclipse.imagen.RenderedOp op = AffineDescriptor.create(source, tx, new InterpolationNearest(),
                new double[] {0}, mask, false, true, null, hints);
        org.eclipse.imagen.ROI result = (org.eclipse.imagen.ROI) op.getProperty("ROI");
        java.awt.Rectangle bounds = op.getBounds();
        try {
            AffineTransform inverse = tx.createInverse();
            for (int y = bounds.y; y < bounds.y + bounds.height; y++) {
                for (int x = bounds.x; x < bounds.x + bounds.width; x++) {
                    java.awt.geom.Point2D point = inverse.transform(new java.awt.geom.Point2D.Double(x + .5, y + .5), null);
                    boolean expected = point.getX() >= 0 && point.getX() < 4 && point.getY() >= 0 && point.getY() < 4;
                    if (result.contains(x, y) != expected) throw new AssertionError("Wrong mask at " + x + "," + y);
                }
            }
        } catch (java.awt.geom.NoninvertibleTransformException e) {
            throw new AssertionError(e);
        } finally {
            op.dispose();
        }
    }

    private static void check(Range r, int min, int max) {
        if (r.getMin().intValue() != min || r.getMax().intValue() != max) {
            throw new AssertionError("Expected [" + min + "," + max + ") but got " + r);
        }
    }
}
