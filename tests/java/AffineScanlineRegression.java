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
        checkPackedMasks();
        checkNoDataMasks();
        checkInteriorMaskGuard();
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

    /** NoData ranges, storage types and any-band-valid semantics match a primitive oracle. */
    private static void checkNoDataMasks() {
        try {
            Class<?> cls = Class.forName("org.geotools.renderer.lite.gridcoverage2d.GridCoverageReaderHelper$NoDataMaskOpImage");
            java.lang.reflect.Constructor<?> constructor = cls.getDeclaredConstructor(
                    java.awt.image.RenderedImage.class, Range.class);
            constructor.setAccessible(true);
            java.lang.reflect.Method compute = cls.getDeclaredMethod("computeRect", java.awt.image.Raster[].class,
                    java.awt.image.WritableRaster.class, java.awt.Rectangle.class);
            compute.setAccessible(true);
            Range[] ranges = {
                org.eclipse.imagen.media.range.RangeFactory.create(0.0, true, 0.0, true, false),
                org.eclipse.imagen.media.range.RangeFactory.create(-10.0, false, 10.0, true, false),
                org.eclipse.imagen.media.range.RangeFactory.create(-10.0f, true, 10.0f, false, true),
                org.eclipse.imagen.media.range.RangeFactory.create(Float.NaN, true, Float.NaN, true, true),
                org.eclipse.imagen.media.range.RangeFactory.createU((short) 65535, true, (short) 65535, true),
                org.eclipse.imagen.media.range.RangeFactory.create((byte) 255, true, (byte) 255, true),
                org.eclipse.imagen.media.range.RangeFactory.create((short) -10, true, (short) 10, true),
                org.eclipse.imagen.media.range.RangeFactory.create(Integer.MAX_VALUE, true, Integer.MAX_VALUE, true)
            };
            double[] values = {0, -10, 10, -9999, 1, 255, 65535, Double.NaN,
                    Double.NEGATIVE_INFINITY, Double.POSITIVE_INFINITY, -0.25, 0.25};
            for (int type : new int[] {0, 1, 2, 3, 4, 5}) {
                for (int bands : new int[] {1, 3, 4}) {
                    java.awt.image.SampleModel sm = new java.awt.image.BandedSampleModel(type, 7, 5, bands);
                    org.eclipse.imagen.TiledImage source = new org.eclipse.imagen.TiledImage(
                            -3, 5, values.length, 9, -5, 3, sm, null);
                    for (int y = 5; y < 14; y++) for (int x = -3; x < values.length - 3; x++) {
                        for (int band = 0; band < bands; band++) {
                            // Include all-equal bands and disagreement between bands.
                            int index = Math.floorMod(x + 3 + (y % 2 == 0 ? band : 0), values.length);
                            source.setSample(x, y, band, values[index]);
                        }
                    }
                    java.awt.image.Raster input = source.getData();
                    for (Range range : ranges) {
                        org.eclipse.imagen.PlanarImage mask = (org.eclipse.imagen.PlanarImage) constructor.newInstance(source, range);
                        java.awt.image.Raster actual = mask.getData();
                        for (int y = 5; y < 14; y++) for (int x = -3; x < values.length - 3; x++) {
                            boolean valid = false;
                            for (int b = 0; b < bands; b++) {
                                double sample = input.getSampleDouble(x, y, b);
                                double min = range.getMin().doubleValue(), max = range.getMax().doubleValue();
                                int rangeType = range.getDataType().getDataType();
                                if (rangeType == java.awt.image.DataBuffer.TYPE_USHORT) {
                                    min = Short.toUnsignedInt(range.getMin().shortValue());
                                    max = Short.toUnsignedInt(range.getMax().shortValue());
                                }
                                boolean floating = rangeType == java.awt.image.DataBuffer.TYPE_FLOAT
                                        || rangeType == java.awt.image.DataBuffer.TYPE_DOUBLE;
                                boolean nodata = Double.isNaN(min) ? Double.isNaN(sample) :
                                        Double.isNaN(sample) ? floating && range.isNanIncluded() :
                                        (sample > min || range.isMinIncluded() && sample == min) &&
                                        (sample < max || range.isMaxIncluded() && sample == max);
                                valid |= !nodata;
                            }
                            if (actual.getSample(x, y, 0) != (valid ? 1 : 0))
                                throw new AssertionError("Wrong NoData mask type=" + type + " bands=" + bands
                                        + " range=" + range + " at " + x + "," + y);
                        }
                        java.awt.image.SampleModel padded = new java.awt.image.PixelInterleavedSampleModel(
                                java.awt.image.DataBuffer.TYPE_BYTE, 17, 9, 1, 21, new int[] {3});
                        java.awt.image.WritableRaster partial = java.awt.image.Raster.createWritableRaster(
                                padded, new java.awt.Point(-5, 5));
                        for (int y = 5; y < 14; y++) for (int x = -5; x < 12; x++) partial.setSample(x, y, 0, 99);
                        java.awt.Rectangle subrect = new java.awt.Rectangle(-2, 6, 5, 7);
                        compute.invoke(mask, new java.awt.image.Raster[] {input}, partial, subrect);
                        for (int y = 5; y < 14; y++) for (int x = -5; x < 12; x++) {
                            int expected = subrect.contains(x, y) ? actual.getSample(x, y, 0) : 99;
                            if (partial.getSample(x, y, 0) != expected)
                                throw new AssertionError("Partial mask write damaged adjacent samples");
                        }
                        mask.dispose();
                    }
                    source.dispose();
                }
            }
        } catch (ReflectiveOperationException e) {
            throw new AssertionError(e);
        }
    }

    private static void checkInteriorMaskGuard() {
        try {
            java.lang.reflect.Method method = Class.forName(
                    "org.geotools.renderer.lite.gridcoverage2d.GridCoverageReaderHelper").getDeclaredMethod(
                    "requestInsideSource", java.awt.Rectangle.class, AffineTransform.class, java.awt.geom.Rectangle2D.class);
            method.setAccessible(true);
            java.awt.Rectangle bounds = new java.awt.Rectangle(-20, 7, 100, 80);
            for (double angle : new double[] {-.7, 0, .3, 1.2}) {
                AffineTransform tx = new AffineTransform();
                tx.translate(1000, -200);
                tx.rotate(angle);
                tx.scale(2, -3);
                for (int x = -40; x <= 100; x += 2) for (int y = -10; y <= 110; y += 2) {
                    java.awt.geom.Point2D world = tx.transform(new java.awt.geom.Point2D.Double(x, y), null);
                    java.awt.geom.Rectangle2D request = new java.awt.geom.Rectangle2D.Double(
                            world.getX() - 5, world.getY() - 5, 10, 10);
                    boolean skip = (Boolean) method.invoke(null, bounds, tx, request);
                    // Independently sample the full request when the fast path is allowed.
                    if (skip) for (int dx = 0; dx <= 10; dx++) for (int dy = 0; dy <= 10; dy++) {
                        java.awt.geom.Point2D p = tx.inverseTransform(new java.awt.geom.Point2D.Double(
                                request.getMinX() + dx, request.getMinY() + dy), null);
                        if (!bounds.contains(p)) throw new AssertionError("Unsafe interior mask bypass");
                    }
                    if (x == 30 && y == 50 && !skip) throw new AssertionError("Interior fast path not used");
                }
            }
            if ((Boolean) method.invoke(null, bounds, new AffineTransform(0, 0, 0, 0, 0, 0),
                    new java.awt.geom.Rectangle2D.Double(0, 0, 1, 1))) throw new AssertionError("Singular transform accepted");
        } catch (ReflectiveOperationException | java.awt.geom.NoninvertibleTransformException e) {
            throw new AssertionError(e);
        }
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

    /** Exact bit sampling for all packed storage types, translated tile grids and padded rows. */
    private static void checkPackedMasks() {
        for (int type : new int[] {java.awt.image.DataBuffer.TYPE_BYTE,
                java.awt.image.DataBuffer.TYPE_USHORT, java.awt.image.DataBuffer.TYPE_INT}) {
            int wordBits = java.awt.image.DataBuffer.getDataTypeSize(type);
            java.awt.image.SampleModel sm = new java.awt.image.MultiPixelPackedSampleModel(
                    type, 37, 29, 1, (37 + 3 + wordBits - 1) / wordBits + 2, 3);
            org.eclipse.imagen.TiledImage source = new org.eclipse.imagen.TiledImage(-11, 7, 37, 29,
                    -15, 3, sm, null);
            for (int y = 7; y < 36; y++) for (int x = -11; x < 26; x++)
                source.setSample(x, y, 0, ((x + 11) / 3 + (y - 7) / 5) & 1);
            for (double angle : new double[] {-0.7, 0.3, 1.2}) {
                AffineTransform tx = new AffineTransform();
                tx.translate(3.125, -8.25);
                tx.rotate(angle);
                tx.scale(1.7, .9);
                AffineGeneralOpImage op = new AffineGeneralOpImage(source,
                        org.eclipse.imagen.BorderExtender.createInstance(org.eclipse.imagen.BorderExtender.BORDER_ZERO),
                        null, null, tx,
                        new org.eclipse.imagen.media.interpolators.InterpolationNearest(null, false, 0, type),
                        false, new double[] {0}, true, null);
                java.awt.Rectangle bounds = op.getBounds();
                java.awt.image.Raster pixels = op.getData();
                try {
                    AffineTransform inverse = tx.createInverse();
                    for (int y = bounds.y; y < bounds.y + bounds.height; y++) {
                        for (int x = bounds.x; x < bounds.x + bounds.width; x++) {
                            java.awt.geom.Point2D point = inverse.transform(new java.awt.geom.Point2D.Double(x + .5, y + .5), null);
                            int sx = (int) Math.floor(point.getX()), sy = (int) Math.floor(point.getY());
                            int expected = sx >= -11 && sx < 26 && sy >= 7 && sy < 36
                                    ? (((sx + 11) / 3 + (sy - 7) / 5) & 1) : 0;
                            if (pixels.getSample(x, y, 0) != expected)
                                throw new AssertionError("Packed mask mismatch type=" + type + " at " + x + "," + y);
                        }
                    }
                } catch (java.awt.geom.NoninvertibleTransformException e) {
                    throw new AssertionError(e);
                } finally { op.dispose(); }
            }
            source.dispose();
        }
    }

    private static void check(Range r, int min, int max) {
        if (r.getMin().intValue() != min || r.getMax().intValue() != max) {
            throw new AssertionError("Expected [" + min + "," + max + ") but got " + r);
        }
    }
}
