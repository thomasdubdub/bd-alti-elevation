from glob import glob
import math
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.colors as colors
from mpl_toolkits.mplot3d import Axes3D
from shapely.geometry import Polygon
from pyproj import Transformer
from scipy.interpolate import interp2d


def get_line_infos(f):
    return float(f.readline().strip().split(" ")[-1])


def get_header_infos(f):
    return [get_line_infos(f) for i in range(6)]


class Dem:
    def __init__(self, folder, center, radius):
        files = folder + "/*.asc"
        self.to_wgs84 = Transformer.from_crs("EPSG:2154", "EPSG:4326")
        self.to_lambert = Transformer.from_crs("EPSG:4326", "EPSG:2154")
        center_lambert = self.to_lambert.transform(center[0], center[1])
        zone_min = (center_lambert[0] - radius, center_lambert[1] - radius)
        zone_max = (center_lambert[0] + radius, center_lambert[1] + radius)
        # Area of interest as a square around center
        self.zone = Polygon(
            [zone_min, (zone_max[0], zone_min[1]), zone_max, (zone_min[0], zone_max[1])]
        )

        tiles = [f for f in glob(files) if self._necessary_tile(f)]
        self.z = np.loadtxt(
            tiles[0], skiprows=6
        )  # to do: manage the case of area of interest between multiple tiles
        with open(tiles[0], "r") as f:
            (ncols, nrows, xll, yll, cellsize, NODATA_value) = get_header_infos(f)

        self.cellsize = cellsize
        self.x = np.linspace(xll, xll + cellsize * ncols, ncols)
        self.y = np.linspace(yll, yll + cellsize * nrows, nrows)
        self.z = self.z[::-1]  # because y from top to bottom in BD ALTI data
        self.lats, self.lons, self.elevation = self.to_wgs84.transform(
            self.x, self.y, self.z
        )
        self.f = interp2d(
            self.x, self.y, self.z, kind="cubic"
        )  # interpolation function

        iminx = math.floor((zone_min[0] - xll) / cellsize)
        imaxx = math.ceil((zone_max[0] - xll) / cellsize)
        iminy = math.floor((zone_min[1] - yll) / cellsize)
        imaxy = math.ceil((zone_max[1] - yll) / cellsize)
        region = np.s_[iminy : imaxy + 1, iminx : imaxx + 1]
        self.X, self.Y, self.Z = self.x[region[1]], self.y[region[0]], self.z[region]
        self.LATS, self.LONS, self.ELEVATION = self.to_wgs84.transform(
            self.X, self.Y, self.Z
        )

    def plot2D_tile(self, color_range=(0.0, 1.0)):
        self._plot(
            self.lons,
            self.lats,
            self.elevation,
            color_range,
            "Lon $[^o E]$",
            "Lat $[^o N]$",
        )

    def plot2D(self, color_range=(0.0, 1.0)):
        self._plot(
            self.LONS,
            self.LATS,
            self.ELEVATION,
            color_range,
            "Lon $[^o E]$",
            "Lat $[^o N]$",
        )

    def plot3D(self, color_range=(0.0, 1.0)):
        colors_land = plt.cm.terrain(np.linspace(color_range[0], color_range[1], 256))
        terrain_map = colors.LinearSegmentedColormap.from_list(
            "terrain_map", colors_land
        )
        xv, yv = np.meshgrid(self.LONS, self.LATS)
        fig = plt.figure(figsize=[12, 8])
        ax = fig.add_subplot(111, projection="3d")
        dem3d = ax.plot_surface(
            xv, yv, self.ELEVATION, cmap=terrain_map
        )  # or plt.get_cmap('gist_earth')
        ax.set_title("DEM")
        ax.set_xlabel("Lon $[^o E]$")
        ax.set_xticklabels([])
        ax.set_ylabel("Lat $[^o N]$")
        ax.set_yticklabels([])
        ax.set_zlabel("Elevation (m)")
        plt.savefig("3D.png")
        plt.show()

    def get_elevation(self, lat, lon):
        c = self.to_lambert.transform(lat, lon)
        return self.f(c[0], c[1])[0]

    def _plot(self, x, y, z, c_range, x_label, y_label):
        colors_land = plt.cm.terrain(np.linspace(c_range[0], c_range[1], 256))
        terrain_map = colors.LinearSegmentedColormap.from_list(
            "terrain_map", colors_land
        )
        fig, ax = plt.subplots(figsize=(12, 10))
        im = ax.pcolormesh(x, y, z, cmap=terrain_map)
        fig.colorbar(im, ax=ax, label="Elevation [m]")
        ax.set_title("DEM")
        ax.set_xlabel(x_label)
        ax.set_ylabel(y_label)
        plt.savefig("2D.png")
        plt.show()

    def _necessary_tile(self, file):
        with open(file, "r") as f:
            (ncols, nrows, xll, yll, cellsize, NODATA_value) = get_header_infos(f)
            x1, y1 = (xll, yll)
            x2, y2 = (xll + cellsize * ncols, yll + cellsize * nrows)
            r = Polygon([(x1, y1), (x2, y1), (x2, y2), (x1, y2)])
            return self.zone.intersects(r)