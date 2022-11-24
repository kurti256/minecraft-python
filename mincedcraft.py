from __future__ import division

import sys
import math
import random
import time

from collections import deque
from pyglet import image
from pyglet.gl import *
from pyglet.graphics import TextureGroup
from pyglet.window import key, mouse

from noise_gen import NoiseGen

TICKS_PER_SEC = 60

# Size of sectors used to ease block loading.
SECTOR_SIZE = 16

# Square root of amount of textures in the image
# When expanding textures.png, make sure it is square, and update this value to
# be the amount of textures you can fit in a single row or column
TEXIMGCOUNT = 16

# Movement variables
WALKING_SPEED = 5
FLYING_SPEED = 15
CROUCH_SPEED = 2
SPRINT_SPEED = 7
SPRINT_FOV = SPRINT_SPEED / 2

GRAVITY = 20.0
MAX_JUMP_HEIGHT = 1.0 # About the height of a block.
# To derive the formula for calculating jump speed, first solve
#    v_t = v_0 + a * t
# for the time at which you achieve maximum height, where a is the acceleration
# due to gravity and v_t = 0. This gives:
#    t = - v_0 / a
# Use t and the desired MAX_JUMP_HEIGHT to solve for v_0 (jump speed) in
#    s = s_0 + v_0 * t + (a * t^2) / 2
JUMP_SPEED = math.sqrt(2 * GRAVITY * MAX_JUMP_HEIGHT)
TERMINAL_VELOCITY = 50

# Player variables
PLAYER_HEIGHT = 2
PLAYER_FOV = 80.0

if sys.version_info[0] >= 3:
    xrange = range

def rot(a):
    th=45
    b = a

    for i in xrange(0,len(a),3):
        b[i] = a[i+2] * math.sin(th) + a[i] * math.cos(th)
        b[i+2] = a[i+2] * math.cos(th) - a[i] * math.sin(th)

    return b

def cube_vertices(x, y, z, n):
    """ Return the vertices of the cube at position x, y, z with size 2*n.
    """
    return rot([
        x-n,y+n,z-n, x-n,y+n,z+n, x+n,y+n,z+n, x+n,y+n,z-n,  # top
        x-n,y-n,z-n, x+n,y-n,z-n, x+n,y-n,z+n, x-n,y-n,z+n,  # bottom
        x-n,y-n,z-n, x-n,y-n,z+n, x-n,y+n,z+n, x-n,y+n,z-n,  # left
        x+n,y-n,z+n, x+n,y-n,z-n, x+n,y+n,z-n, x+n,y+n,z+n,  # right
        x-n,y-n,z+n, x+n,y-n,z+n, x+n,y+n,z+n, x-n,y+n,z+n,  # front
        x+n,y-n,z-n, x-n,y-n,z-n, x-n,y+n,z-n, x+n,y+n,z-n,  # back
    ])

def water_vertices(x, y, z, n):
    """ Return the vertices of the cube at position x, y, z with size 2*n.
    """
    a = 0.2
    b = 0.8
    
    return [
        x-n,y+n-a,z-n, x-n,y+n-a,z+n, x+n,y+n-a,z+n, x+n,y+n-a,z-n,  # top
        x-n,y-n+b,z-n, x+n,y-n+b,z-n, x+n,y-n+b,z+n, x-n,y-n+b,z+n,  # bottom
        0,0,0, 0,0,0, 0,0,0, 0,0,0,   # left
        0,0,0, 0,0,0, 0,0,0, 0,0,0,   # right
        0,0,0, 0,0,0, 0,0,0, 0,0,0,   # front
        0,0,0, 0,0,0, 0,0,0, 0,0,0,   # back
    ]

def slab_vertices(x, y, z, n):
    """ Return the vertices of the cube at position x, y, z with size 2*n.
    """
    m = n/2
    j=0.25
    k=0.5
    
    return [
        x-n,y+n-k,z-n, x-n,y+n-k,z+n, x+n,y+n-k,z+n, x+n,y+n-k,z-n,  # top
        x-n,y-n,z-n, x+n,y-n,z-n, x+n,y-n,z+n, x-n,y-n,z+n,  # bottom
        x-n,y-m-j,z-n, x-n,y-m-j,z+n, x-n,y+m-j,z+n, x-n,y+m-j,z-n,  # left
        x+n,y-m-j,z+n, x+n,y-m-j,z-n, x+n,y+m-j,z-n, x+n,y+m-j,z+n,  # right
        x-n,y-m-j,z+n, x+n,y-m-j,z+n, x+n,y+m-j,z+n, x-n,y+m-j,z+n,  # front
        x+n,y-m-j,z-n, x-n,y-m-j,z-n, x-n,y+m-j,z-n, x+n,y+m-j,z-n,  # back
    ]

def plant_verts(x, y, z, n):
    """ Return the vertices of the cube at position x, y, z with size 2*n.
    """
    return [
        0,0,0, 0,0,0, 0,0,0, 0,0,0, 
        0,0,0, 0,0,0, 0,0,0, 0,0,0, 
        x-n,y-n,z-n, x+n,y-n,z+n, x+n,y+n,z+n, x-n,y+n,z-n,  # left
        x+n,y-n,z+n, x-n,y-n,z-n, x-n,y+n,z-n, x+n,y+n,z+n,  # right
        x-n,y-n,z+n, x+n,y-n,z-n, x+n,y+n,z-n, x-n,y+n,z+n,  # front
        x+n,y-n,z-n, x-n,y-n,z+n, x-n,y+n,z+n, x+n,y+n,z-n,  # back
    ]


def tex_coord(x, y, n=TEXIMGCOUNT):
    """ Return the bounding vertices of the texture square.
    """
    m = 1.0 / n
    dx = x * m
    dy = y * m
    return dx, dy, dx + m, dy, dx + m, dy + m, dx, dy + m

def tex_coord_slab(x, y, n=TEXIMGCOUNT):
    """ Return the bounding vertices of the texture square.
    """
    m = 1.0 / n
    l = 0.5 / n
    dx = x * m
    dy = y * m
    return dx, dy, dx + m, dy, dx + m, dy + l, dx, dy + l


def tex_coords(top, bottom, side):
    """ Return a list of the texture squares for the top, bottom and side.
    """
    top = tex_coord(*top)
    bottom = tex_coord(*bottom)
    side = tex_coord(*side)
    result = []
    result.extend(top)
    result.extend(bottom)
    result.extend(side * 4)
    return result

def tex_full(top, bottom, left, right, front, back):
    top = tex_coord(*top)
    bottom = tex_coord(*bottom)
    left = tex_coord(*left)
    right = tex_coord(*right)
    front = tex_coord(*front)
    back = tex_coord(*back)
    result = []
    result.extend(top)
    result.extend(bottom)
    result.extend(left)
    result.extend(right)
    result.extend(front)
    result.extend(back)
    return result

def tex_s(tex):
    tex = tex_coord(*tex)
    result = []
    result.extend(tex * 6)
    return result

def tex_slab(top, bottom, side):
    top = tex_coord(*top)
    bottom = tex_coord(*bottom)
    side = tex_coord_slab(*side)
    result = []
    result.extend(top)
    result.extend(bottom)
    result.extend(side * 4)
    return result
    


TEXTURE_PATH = 'texture.png'

#blocks

bids = {
    "stone": tex_s((2, 1)),
    "stone_slab": tex_slab((2, 1), (2, 1), (2, 1)),
    "bedrock": tex_s((7, 1)),
    "cobble": tex_s((1, 2)),
    "cobble_slab": tex_slab((1, 2), (1, 2), (1, 2)),
    "mossy_cobble": tex_s((5, 1)),
    "mossy_cobble_slab": tex_slab((5, 1), (5, 1), (5, 1)),
    
    "coal_ore": tex_s((4, 0)),
    "iron_ore": tex_s((5, 0)),
    "gold_ore": tex_s((6, 0)),
    "diamond_ore": tex_s((7, 0)),
    "emerald_ore": tex_s((6, 1)),
    
    "sand": tex_s((1, 1)),
    "sandstone": tex_coords((2, 3), (0, 3), (1, 3)),
    "sandstone_slab": tex_slab((2, 3), (0, 3), (1, 3)),
    "smooth_sandstone": tex_s((2, 3)),
    "smooth_sandstone_slab": tex_slab((2, 3), (2, 3), (2, 3)),
    "glass": tex_s((3, 3)),
    "obsidian": tex_s((3, 4)),
    
    "dirt": tex_s((0, 1)),
    "grass": tex_coords((1, 0), (0, 1), (0, 0)),
    "podzol": tex_coords((6, 4), (0, 1), (5, 4)),
    
    "tall_grass": tex_s((4, 1)),
    "dandelion": tex_s((4, 2)),
    "poppy": tex_s((4, 3)),
    "azure": tex_s((5, 3)),
    "orchid": tex_s((6, 3)),
    "allium": tex_s((7, 3)),
    "cornflower": tex_s((7, 4)),
    "fern": tex_s((4, 4)),

    "pumpkin": tex_coords((3, 5), (3, 5), (2, 5)),
    
    "oak_log": tex_coords((3, 2), (3, 2), (3, 1)),
    "oak_leaves": tex_s((3, 0)),
    "oak_planks": tex_s((2, 2)),
    "oak_plank_slab": tex_slab((2, 2), (2, 2), (2, 2)),
    
    "birch_log": tex_coords((1, 7), (1, 7), (0, 7)),
    "birch_leaves": tex_s((2, 7)),
    "birch_planks": tex_s((3, 7)),
    "birch_plank_slab": tex_slab((3, 7), (3, 7), (3, 7)),

    "spruce_log": tex_coords((1, 6), (1, 6), (0, 6)),
    "spruce_leaves": tex_s((2, 6)),
    "spruce_planks": tex_s((3, 6)),
    "spruce_plank_slab": tex_slab((3, 6), (3, 6), (3, 6)),

    "jungle_log": tex_coords((5, 7), (5, 7), (4, 7)),
    "jungle_leaves": tex_s((6, 7)),
    "jungle_planks": tex_s((7, 7)),
    "jungle_plank_slab": tex_slab((7, 7), (7, 7), (7, 7)),

    "acacia_log": tex_coords((5, 6), (5, 6), (4, 6)),
    "acacia_leaves": tex_s((6, 6)),
    "acacia_planks": tex_s((7, 6)),
    "acacia_plank_slab": tex_slab((7, 6), (7, 6), (7, 6)),

    "doak_log": tex_coords((5, 5), (5, 5), (4, 5)),
    "doak_leaves": tex_s((6, 5)),
    "doak_planks": tex_s((7, 5)),
    "doak_plank_slab": tex_slab((7, 5), (7, 5), (7, 5)),
    
    "bricks": tex_s((2, 0)),
    "brick_slab": tex_slab((2, 0), (2, 0), (2, 0)),
    "stone_brick": tex_s((5, 2)),
    "stone_brick_slab": tex_slab((5, 2), (5, 2), (5, 2)),
    "cracked_stone_brick": tex_s((6, 2)),
    "cracked_stone_brick_slab": tex_slab((6, 2), (6, 2), (6, 2)),
    "mossy_stone_brick": tex_s((7, 2)),
    "mossy_stone_brick_slab": tex_slab((7, 2), (7, 2), (7, 2)),
    "smooth_stone": tex_s((8, 0)),
    "smooth_stone_slab": tex_slab((8, 0), (8, 0), (9, 0)),

    "furnace": tex_full((10, 0), (10, 0), (11, 0), (11, 0), (12, 0), (11, 0)),
    
    "water": tex_s((0, 2)),
    
    "tnt": tex_coords((2, 4), (0, 4), (1, 4)),
    "sponge": tex_s((0, 5)),
    "wet_sponge": tex_s((1, 5))
}

#block properties
#since blocks are defined by texture only,
#i decided to use lists of block id's attributed
#to properties, instead of the other way round

#blocks do not cull other blocks
SEETHR = [
    "tall_grass",
    "oak_plank_slab",
    "birch_plank_slab",
    "spruce_plank_slab",
    "jungle_plank_slab",
    "acacia_plank_slab",
    "doak_plank_slab",
    "cobble_slab",
    "mossy_cobble_slab",
    "brick_slab",
    "stone_slab",
    "sandstone_slab",
    "smooth_sandstone_slab",
    "stone_brick_slab",
    "cracked_stone_brick_slab",
    "mossy_stone_brick_slab",
    "smooth_stone_slab",
    "dandelion",
    "poppy",
    "azure",
    "orchid",
    "allium",
    "cornflower",
    "fern",
]

#blocks only cull blocks of the same type
GROUPCULL = [
    "water",
    "oak_leaves",
    "birch_leaves",
    "spruce_leaves",
    "jungle_leaves",
    "acacia_leaves",
    "doak_leaves",
    "glass",
]

#blocks use a cross shape
PLANTB = [
    "tall_grass",
    "dandelion",
    "poppy",
    "azure",
    "orchid",
    "allium",
    "cornflower",
    "fern",
]

#blocks can have plants placed on them
PLANTER = [
    "grass",
    "dirt",
    "podzol",
]

#blocks are plants and can only be placed on planter blocks
PLANTEE = [
    "tall_grass",
    "dandelion",
    "poppy",
    "azure",
    "orchid",
    "allium",
    "cornflower",
    "fern",
]

#blocks use the water block model
WATERB = [
    "water",
]

#blocks do not collide with the player
THRU = [
    "tall_grass",
    "water",
    "dandelion",
    "poppy",
    "azure",
    "orchid",
    "allium",
    "cornflower",
    "fern",
]

#blocks do not get hit by punches
# !NOT IMPLEMENTED!
PUNCHTHRU = [
    "water",
]

#blocks you can swim in
# !NOT IMPLEMENTED!
SWIM = [
    "water",
]

#blocks will be overwritten when blocks are placed on it
REPLACE = [
    "tall_grass",
    "fern",
]

#blocks blend in batch2
RENDERLATE = [
    "water",
]

#blocks use the slab model
# !NOT FULLY IMPLEMENTED!
SLAB = [
    "oak_plank_slab",
    "birch_plank_slab",
    "spruce_plank_slab",
    "jungle_plank_slab",
    "acacia_plank_slab",
    "doak_plank_slab",
    "cobble_slab",
    "mossy_cobble_slab",
    "brick_slab",
    "stone_slab",
    "sandstone_slab",
    "smooth_sandstone_slab",
    "stone_brick_slab",
    "cracked_stone_brick_slab",
    "mossy_stone_brick_slab",
    "smooth_stone_slab",
]

#blocks are not broken by tnt
TNTRESIST = [
    "bedrock",
    "water",
    "obsidian",
]


FACES = [
    ( 0, 1, 0), #top
    ( 0,-1, 0), #bottom
    (-1, 0, 0), #left
    ( 1, 0, 0), #right
    ( 0, 0, 1), #front
    ( 0, 0,-1), #back
]


def normalize(position):
    """ Accepts `position` of arbitrary precision and returns the block
    containing that position.
    Parameters
    ----------
    position : tuple of len 3
    Returns
    -------
    block_position : tuple of ints of len 3
    """
    x, y, z = position
    x, y, z = (int(round(x)), int(round(y)), int(round(z)))
    return (x, y, z)


def sectorize(position):
    """ Returns a tuple representing the sector for the given `position`.
    Parameters
    ----------
    position : tuple of len 3
    Returns
    -------
    sector : tuple of len 3
    """
    x, y, z = normalize(position)
    x, y, z = x // SECTOR_SIZE, y // SECTOR_SIZE, z // SECTOR_SIZE
    return (x, 0, z)


class Model(object):

    def __init__(self):

        # A Batch is a collection of vertex lists for batched rendering.
        self.batch = pyglet.graphics.Batch()
        self.batch2 = pyglet.graphics.Batch()
        
        # A TextureGroup manages an OpenGL texture.
        self.group = TextureGroup(image.load(TEXTURE_PATH).get_texture())

        # A mapping from position to the texture of the block at that position.
        # This defines all the blocks that are currently in the world.
        self.world = {}

        # Same mapping as `world` but only contains blocks that are shown.
        self.shown = {}

        # Mapping from position to a pyglet `VertextList` for all shown blocks.
        self._shown = {}

        # Mapping from sector to a list of positions inside that sector.
        self.sectors = {}

        # Simple function queue implementation. The queue is populated with
        # _show_block() and _hide_block() calls
        self.queue = deque()

        self._initialize()

    def _initialize(self):
        """ Initialize the world by placing all the blocks.
        """

        seed = 88960
        gen = NoiseGen(seed)
        random.seed(seed)

        stonearea = {}
        podzols = {}

        n = 128 #size of the world
        s = 1  # step size
        y = 50  # initial y height
        
        #too lazy to do this properly lol
        heightMap = []
        for x in xrange(0, n, s):
            for z in xrange(0, n, s):
                heightMap.append(0)
        for x in xrange(0, n, s):
            for z in xrange(0, n, s):
                heightMap[z + x * n] = int(gen.getHeight(x, z))

        for x in xrange(0,n,s):
            for z in xrange(0,n,s):
                for y in xrange(0, 255, s):
                    stonearea[(x, y, z)] = False
                podzols[(x,z)] = False
                if random.randrange(0,1000) > 998:
                    for px in xrange(-4,4):
                        for pz in xrange(-4,4):
                            podzols[(x+px,z+pz)] = True

        #Generate the world
        for x in xrange(0, n, s):
            for z in xrange(0, n, s):
                h = heightMap[z + x * n]
                if (h < 33):
                    #water
                    for y in range (h, 31):
                        self.add_block((x, y, z), "water", immediate=False)
                    #sand
                    self.add_block((x, h, z), "sand", immediate=False)
                    for y in xrange(h - 1, 0, -1):
                        if y > h-random.randrange(2,4):
                            self.add_block((x, y, z), "sand", immediate=False)
                        elif y > h-random.randrange(3,7):
                            self.add_block((x, y, z), "sandstone", immediate=False)
                        else:
                            self.add_block((x, y, z), "stone", immediate=False)
                            stonearea[(x, y, z)] = True
                    continue
                #grass
                if podzols[(x,z)] == True:
                    self.add_block((x, h, z), "podzol", immediate=False)
                else:
                    self.add_block((x, h, z), "grass", immediate=False)
                for y in xrange(h - 1, 0, -1):
                    if y > h-random.randrange(2,6):
                        self.add_block((x, y, z), "dirt", immediate=False)
                    else:
                        self.add_block((x, y, z), "stone", immediate=False)
                        stonearea[(x, y, z)] = True
                #Maybe add tree at this (x, z)
                if (h > 20):
                    #plants
                    if random.randrange(0, 1000) > 995:
                        self.add_block((x, h+1, z), "fern", immediate=False)
                    if random.randrange(0, 1000) > 880:
                        self.add_block((x, h+1, z), "tall_grass", immediate=False)
                    if random.randrange(0, 1000) > 950:
                        self.add_block((x, h+1, z), "dandelion", immediate=False)
                    if random.randrange(0, 1000) > 950:
                        flist = ["poppy", "azure", "orchid", "allium", "cornflower"]
                        self.add_block((x, h+1, z), flist[(x+z)%(len(flist))], immediate=False)
                    if random.randrange(0, 1000) > 998:
                        self.add_block((x, h+1, z), "pumpkin", immediate=False)
                    if random.randrange(0, 1000) > 990:
                        treeHeight = random.randrange(4, 9)
                        typs = ["oak","birch","spruce","jungle","acacia","doak"]
                        typ = typs[random.randrange(0,5)]
                        #Tree leaves
                        leafh = h + treeHeight - 2
                        leaft = 3
                        leafw = 3
                        if typ=="acacia":
                            treeHeight -= 2
                            leaft = 1
                            leafw = 4
                        for lz in xrange(z + 1 - leafw, z + leafw):
                            for lx in xrange(x + 1 - leafw, x + leafw): 
                                for ly in xrange(leaft):
                                    self.add_block((lx, leafh + ly, lz), (typ+"_leaves"), immediate=False)
                        #Tree trunk
                        for y in xrange(h + 1, h + treeHeight):
                            self.add_block((x, y, z), (typ+"_log"), immediate=False)
        #ores
        for x in xrange(0,n,s):
            for z in xrange(0,n,s):
                #coal
                ry = random.randrange(1,100)
                rh = random.randrange(1,8)
                for gh in xrange(ry, ry+rh, 1):
                    rpos = x, gh, z
                    if stonearea[rpos] == True:
                        self.add_block(rpos, "coal_ore", immediate=False)
                #iron
                if random.randrange(0, 1000) > 100:
                    ry = random.randrange(1,100)
                    rh = random.randrange(1,8)
                    for gh in xrange(ry, ry+rh, 1):
                        rpos = x, gh, z
                        if stonearea[rpos] == True:
                            self.add_block(rpos, "iron_ore", immediate=False)
                #gold
                if random.randrange(0, 1000) > 990:
                    ry = random.randrange(1,20)
                    rpos = x, ry, z
                    if stonearea[rpos] == True:
                        self.add_block(rpos, "gold_ore", immediate=False)
                #diamond
                if random.randrange(0, 1000) > 997:
                    ry = random.randrange(1,12)
                    rh = random.randrange(1,3)
                    for gh in xrange(ry, ry+rh, 1):
                        rpos = x, gh, z
                        if stonearea[rpos] == True:
                            self.add_block(rpos, "diamond_ore", immediate=False)
                #emerald
                if random.randrange(0, 1000) > 998:
                    ry = random.randrange(1,80)
                    rpos = x, ry, z
                    if stonearea[rpos] == True:
                        self.add_block(rpos, "emerald_ore", immediate=False)
        #bedrock
        for x in xrange(0,n,s):
            for z in xrange(0,n,s):
                self.add_block((x,0,z), "bedrock", immediate=False)
                if (x*z)%8<(x+z)%3:
                    self.add_block((x,1,z), "bedrock", immediate=False)
                if (x*z)%6<(x+z*2)%5:
                    self.add_block((x,2,z), "bedrock", immediate=False)
                    

    def hit_test(self, position, vector, max_distance=8):
        """ Line of sight search from current position. If a block is
        intersected it is returned, along with the block previously in the line
        of sight. If no block is found, return None, None.
        Parameters
        ----------
        position : tuple of len 3
            The (x, y, z) position to check visibility from.
        vector : tuple of len 3
            The line of sight vector.
        max_distance : int
            How many blocks away to search for a hit.
        """
        m = 8
        x, y, z = position
        dx, dy, dz = vector
        previous = None
        for _ in xrange(max_distance * m):
            key = normalize((x, y, z))
            if key != previous and key in self.world:
                return key, previous
            previous = key
            x, y, z = x + dx / m, y + dy / m, z + dz / m
        return None, None

    def exposed(self, position):
        """ Returns False is given `position` is surrounded on all 6 sides by
        blocks, True otherwise.
        """
        x, y, z = position
        for dx, dy, dz in FACES:
            key = x + dx, y + dy, z + dz
            if key not in self.world:
                return True
            if self.world[key] in SEETHR:
                return True
            if self.world[key] in GROUPCULL:
                if self.world[key] != self.world[position]:
                    return True
        return False

    def add_block(self, position, bid, immediate=True):
        """ Add a block with the given `texture` and `position` to the world.
        Parameters
        ----------
        position : tuple of len 3
            The (x, y, z) position of the block to add.
        texture : list of len 3
            The coordinates of the texture squares. Use `tex_coords()` to
            generate.
        immediate : bool
            Whether or not to draw the block immediately.
        """
        x, y, z = position
        if not (bid in PLANTEE and (self.world[x, y-1, z] not in PLANTER or (x, y-1, z) not in self.world)):
            if position in self.world:
                self.remove_block(position, immediate)
            self.world[position] = bid
            self.sectors.setdefault(sectorize(position), []).append(position)
            if immediate:
                if self.exposed(position):
                    self.show_block(position)
                #if bid not in SEETHR:
                self.check_neighbors(position)

    def remove_block(self, position, immediate=True):
        """ Remove the block at the given `position`.
        Parameters
        ----------
        position : tuple of len 3
            The (x, y, z) position of the block to remove.
        immediate : bool
            Whether or not to immediately remove block from canvas.
        """
        del self.world[position]
        self.sectors[sectorize(position)].remove(position)
        if immediate:
            if position in self.shown:
                self.hide_block(position)
            self.check_neighbors(position)

    def check_neighbors(self, position):
        """ Check all blocks surrounding `position` and ensure their visual
        state is current. This means hiding blocks that are not exposed and
        ensuring that all exposed blocks are shown. Usually used after a block
        is added or removed.
        """
        
        x, y, z = position
        for dx, dy, dz in FACES:
            key = (x + dx, y + dy, z + dz)
            if key not in self.world:
                continue
            if self.exposed(key):
                if key not in self.shown:
                    self.show_block(key)
            else:
                if key in self.shown:
                    self.hide_block(key)

    def show_block(self, position, immediate=True):
        """ Show the block at the given `position`. This method assumes the
        block has already been added with add_block()
        Parameters
        ----------
        position : tuple of len 3
            The (x, y, z) position of the block to show.
        immediate : bool
            Whether or not to show the block immediately.
        """
        
        bid = self.world[position]
        self.shown[position] = bid
        
        if immediate:
            self._show_block_typed(position, bid)
        else:
            self._enqueue(self._show_block_typed, position, bid)

    def _show(self, position, bid, vtx, tex):
        if bid in RENDERLATE:
            self._shown[position] = self.batch2.add(24, GL_QUADS, self.group,
                ('v3f/static', vtx),
                ('t2f/static', tex))
        else:
            self._shown[position] = self.batch.add(24, GL_QUADS, self.group,
                ('v3f/static', vtx),
                ('t2f/static', tex))

    def _show_block_typed(self, position, bid):
        if bid in PLANTB:
            self._show_grass_block(position, bid)
        elif bid in SLAB:
            self._show_slab(position, bid)
        elif bid in WATERB:
            self._show_water(position, bid)
        else:
            self._show_block(position, bid)

    def _show_block(self, position, bid):
        """ Private implementation of the `show_block()` method.
        Parameters
        ----------
        position : tuple of len 3
            The (x, y, z) position of the block to show.
        texture : list of len 3
            The coordinates of the texture squares. Use `tex_coords()` to
            generate.
        """
        x, y, z = position
        vertex_data = cube_vertices(x, y, z, 0.5)
        texture_data = list(bids[bid])
        # create vertex list
        # FIXME Maybe `add_indexed()` should be used instead
        self._show(position, bid, vertex_data, texture_data)

    def _show_water(self, position, bid):
        """ Private implementation of the `show_block()` method.
        Parameters
        ----------
        position : tuple of len 3
            The (x, y, z) position of the block to show.
        texture : list of len 3
            The coordinates of the texture squares. Use `tex_coords()` to
            generate.
        """
        x, y, z = position
        vertex_data = water_vertices(x, y, z, 0.5)
        texture_data = list(bids[bid])
        # create vertex list
        # FIXME Maybe `add_indexed()` should be used instead
        self._show(position, bid, vertex_data, texture_data)

    def _show_grass_block(self, position, bid):
        x, y, z = position
        vertex_data = plant_verts(x, y, z, 0.5)
        texture_data = list(bids[bid])
        # create vertex list
        # FIXME Maybe `add_indexed()` should be used instead
        self._show(position, bid, vertex_data, texture_data)

    def _show_slab(self, position, bid):
        """ Private implementation of the `show_block()` method.
        Parameters
        ----------
        position : tuple of len 3
            The (x, y, z) position of the block to show.
        texture : list of len 3
            The coordinates of the texture squares. Use `tex_coords()` to
            generate.
        """
        x, y, z = position
        vertex_data = slab_vertices(x, y, z, 0.5)
        texture_data = list(bids[bid])
        # create vertex list
        # FIXME Maybe `add_indexed()` should be used instead
        self._show(position, bid, vertex_data, texture_data)

    def hide_block(self, position, immediate=True):
        """ Hide the block at the given `position`. Hiding does not remove the
        block from the world.
        Parameters
        ----------
        position : tuple of len 3
            The (x, y, z) position of the block to hide.
        immediate : bool
            Whether or not to immediately remove the block from the canvas.
        """
        self.shown.pop(position)
        if immediate:
            self._hide_block(position)
        else:
            self._enqueue(self._hide_block, position)

    def _hide_block(self, position):
        """ Private implementation of the 'hide_block()` method.
        """
        self._shown.pop(position).delete()

    def show_sector(self, sector):
        """ Ensure all blocks in the given sector that should be shown are
        drawn to the canvas.
        """
        for position in self.sectors.get(sector, []):
            if position not in self.shown and self.exposed(position):
                self.show_block(position, False)

    def hide_sector(self, sector):
        """ Ensure all blocks in the given sector that should be hidden are
        removed from the canvas.
        """
        for position in self.sectors.get(sector, []):
            if position in self.shown:
                self.hide_block(position, False)

    def change_sectors(self, before, after):
        """ Move from sector `before` to sector `after`. A sector is a
        contiguous x, y sub-region of world. Sectors are used to speed up
        world rendering.
        """
        before_set = set()
        after_set = set()
        pad = 4
        for dx in xrange(-pad, pad + 1):
            for dy in [0]:  # xrange(-pad, pad + 1):
                for dz in xrange(-pad, pad + 1):
                    if dx ** 2 + dy ** 2 + dz ** 2 > (pad + 1) ** 2:
                        continue
                    if before:
                        x, y, z = before
                        before_set.add((x + dx, y + dy, z + dz))
                    if after:
                        x, y, z = after
                        after_set.add((x + dx, y + dy, z + dz))
        show = after_set - before_set
        hide = before_set - after_set
        for sector in show:
            self.show_sector(sector)
        for sector in hide:
            self.hide_sector(sector)

    def _enqueue(self, func, *args):
        """ Add `func` to the internal queue.
        """
        self.queue.append((func, args))

    def _dequeue(self):
        """ Pop the top function from the internal queue and call it.
        """
        func, args = self.queue.popleft()
        func(*args)

    def process_queue(self):
        """ Process the entire queue while taking periodic breaks. This allows
        the game loop to run smoothly. The queue contains calls to
        _show_block() and _hide_block() so this method should be called if
        add_block() or remove_block() was called with immediate=False
        """
        start = time.process_time()
        while self.queue and time.process_time() - start < 1.0 / TICKS_PER_SEC:
            self._dequeue()

    def process_entire_queue(self):
        """ Process the entire queue with no breaks.
        """
        while self.queue:
            self._dequeue()


class Window(pyglet.window.Window):

    def __init__(self, *args, **kwargs):
        super(Window, self).__init__(*args, **kwargs)

        # Whether or not the window exclusively captures the mouse.
        self.exclusive = False

        # When flying gravity has no effect and speed is increased.
        self.flying = False

        # Used for constant jumping. If the space bar is held down,
        # this is true, otherwise, it's false
        self.jumping = False

        # If the player actually jumped, this is true
        self.jumped = False

        # If this is true, a crouch offset is added to the final glTranslate
        self.crouch = False

        # Player sprint
        self.sprinting = False

        # Player swimming
        self.swimming = False

        # This is an offset value so stuff like speed potions can also be easily added
        self.fov_offset = 0

        self.collision_types = {"top": False, "bottom": False, "right": False, "left": False}

        # Strafing is moving lateral to the direction you are facing,
        # e.g. moving to the left or right while continuing to face forward.
        #
        # First element is -1 when moving forward, 1 when moving back, and 0
        # otherwise. The second element is -1 when moving left, 1 when moving
        # right, and 0 otherwise.
        self.strafe = [0, 0]

        # Current (x, y, z) position in the world, specified with floats. Note
        # that, perhaps unlike in math class, the y-axis is the vertical axis.
        self.position = (30, 80, 80)

        # First element is rotation of the player in the x-z plane (ground
        # plane) measured from the z-axis down. The second is the rotation
        # angle from the ground plane up. Rotation is in degrees.
        #
        # The vertical plane rotation ranges from -90 (looking straight down) to
        # 90 (looking straight up). The horizontal rotation range is unbounded.
        self.rotation = (0, 0)

        # Which sector the player is currently in.
        self.sector = None

        # The crosshairs at the center of the screen.
        self.reticle = None

        # Velocity in the y (upward) direction.
        self.dy = 0

        # A list of blocks the player can place. Hit num keys to cycle.
        self.inventory = ["stone","stone_slab","cobble","cobble_slab","mossy_cobble","mossy_cobble_slab",
                          "coal_ore","iron_ore","gold_ore","diamond_ore","emerald_ore","obsidian",
                          "bricks","brick_slab",
                          "stone_brick","stone_brick_slab","cracked_stone_brick","cracked_stone_brick_slab","mossy_stone_brick","mossy_stone_brick_slab",
                          "smooth_stone", "smooth_stone_slab",
                          "dirt","grass","tall_grass","fern","dandelion","poppy","azure","orchid","allium","cornflower",
                          "pumpkin",
                          "oak_log","oak_planks","oak_plank_slab","oak_leaves",
                          "birch_log","birch_planks","birch_plank_slab","birch_leaves",
                          "spruce_log","spruce_planks","spruce_plank_slab","spruce_leaves",
                          "jungle_log","jungle_planks","jungle_plank_slab","jungle_leaves",
                          "acacia_log","acacia_planks","acacia_plank_slab","acacia_leaves",
                          "doak_log","doak_planks","doak_plank_slab","doak_leaves",
                          "sand","sandstone","sandstone_slab","smooth_sandstone","smooth_sandstone_slab",
                          "furnace",
                          "glass","water","bedrock","sponge","wet_sponge","tnt"]
        
        self.invstr = ["Stone","Stone Slab","Cobblestone","Cobblestone Slab","Mossy Cobblestone", "Mossy Cobblestone Slab",
                       "Coal Ore","Iron Ore","Gold Ore","Diamond Ore","Emerald Ore","Obsidian",
                       "Bricks","Brick Slab",
                       "Stone Brick", "Stone Brick Slab", "Cracked Stone Brick", "Cracked Stone Brick Slab", "Mossy Stone Brick", "Mossy Stone Brick Slab",
                       "Smooth Stone", "Smooth Stone Slab",
                       "Dirt","Grass Block","Grass","Fern","Dandelion","Poppy","Azure Bulet","Orchids","Allium","Cornfower",
                       "Pumpkin",
                       "Oak Log","Oak Planks","Oak Slab","Oak Leaves",
                       "Birch Log","Birch Planks","Birch Slab","Birch Leaves",
                       "Spruce Log","Spruce Planks","Spruce Slab","Spruce Leaves",
                       "Jungle Log","Jungle Planks","Jungle Slab","Jungle Leaves",
                       "Acacia Log","Acacia Planks","Acacia Slab","Acacia Leaves",
                       "Dark Oak Log","Dark Oak Planks","Dark Oak Slab","Dark Oak Leaves",
                       "Sand","Sandstone","Sandstone Slab","Smooth Sandstone","Smooth Sandstone Slab",
                       "Furnace",
                       "Glass Block","Water Block","Bedrock","Sponge","Wet Sponge","TNT"]

        # The current block the user can place. Hit num keys to cycle.
        self.bindx = 0
        self.block = self.inventory[self.bindx]

        self.blabel = pyglet.text.Label('', font_name='Arial', font_size=18,
            x=10, y=self.height - 28, anchor_x='left', anchor_y='top',
            color=(0, 0, 0, 255))

        # Convenience list of num keys.
        self.num_keys = [
            key._1, key._2, key._3, key._4, key._5,
            key._6, key._7, key._8, key._9, key._0]

        # Instance of the model that handles the world.
        self.model = Model()

        # The label that is displayed in the top left of the canvas.
        self.label = pyglet.text.Label('', font_name='Arial', font_size=18,
            x=10, y=self.height - 10, anchor_x='left', anchor_y='top',
            color=(0, 0, 0, 255))

        # This call schedules the `update()` method to be called
        # TICKS_PER_SEC. This is the main game event loop.
        pyglet.clock.schedule_interval(self.update, 1.0 / TICKS_PER_SEC)

    def set_exclusive_mouse(self, exclusive):
        """ If `exclusive` is True, the game will capture the mouse, if False
        the game will ignore the mouse.
        """
        super(Window, self).set_exclusive_mouse(exclusive)
        self.exclusive = exclusive

    def get_sight_vector(self):
        """ Returns the current line of sight vector indicating the direction
        the player is looking.
        """
        x, y = self.rotation
        # y ranges from -90 to 90, or -pi/2 to pi/2, so m ranges from 0 to 1 and
        # is 1 when looking ahead parallel to the ground and 0 when looking
        # straight up or down.
        m = math.cos(math.radians(y))
        # dy ranges from -1 to 1 and is -1 when looking straight down and 1 when
        # looking straight up.
        dy = math.sin(math.radians(y))
        dx = math.cos(math.radians(x - 90)) * m
        dz = math.sin(math.radians(x - 90)) * m
        return (dx, dy, dz)

    def get_motion_vector(self):
        """ Returns the current motion vector indicating the velocity of the
        player.
        Returns
        -------
        vector : tuple of len 3
            Tuple containing the velocity in x, y, and z respectively.
        """
        if any(self.strafe):
            x, y = self.rotation
            strafe = math.degrees(math.atan2(*self.strafe))
            y_angle = math.radians(y)
            x_angle = math.radians(x + strafe)
            if self.flying:
                m = math.cos(y_angle)
                dy = math.sin(y_angle)
                if self.strafe[1]:
                    # Moving left or right.
                    dy = 0.0
                    m = 1
                if self.strafe[0] > 0:
                    # Moving backwards.
                    dy *= -1
                # When you are flying up or down, you have less left and right
                # motion.
                dx = math.cos(x_angle) * m
                dz = math.sin(x_angle) * m
            else:
                dy = 0.0
                dx = math.cos(x_angle)
                dz = math.sin(x_angle)
        else:
            dy = 0.0
            dx = 0.0
            dz = 0.0
        return (dx, dy, dz)

    def update(self, dt):
        """ This method is scheduled to be called repeatedly by the pyglet
        clock.
        Parameters
        ----------
        dt : float
            The change in time since the last call.
        """
        self.model.process_queue()
        sector = sectorize(self.position)
        if sector != self.sector:
            self.model.change_sectors(self.sector, sector)
            if self.sector is None:
                self.model.process_entire_queue()
            self.sector = sector
        m = 8
        dt = min(dt, 0.2)
        for _ in xrange(m):
            self._update(dt / m)

    def _update(self, dt):
        """ Private implementation of the `update()` method. This is where most
        of the motion logic lives, along with gravity and collision detection.
        Parameters
        ----------
        dt : float
            The change in time since the last call.
        """
        # walking
        if self.flying:
            speed = FLYING_SPEED
        elif self.sprinting:
            speed = SPRINT_SPEED
        elif self.crouch:
            speed = CROUCH_SPEED
        else:
            speed = WALKING_SPEED

        if self.jumping:
            if self.collision_types["top"]:
                self.dy = JUMP_SPEED
                self.jumped = True
        else:
            if self.collision_types["top"]:
                self.jumped = False
        if self.jumped:
            speed += 0.7

        d = dt * speed # distance covered this tick.
        dx, dy, dz = self.get_motion_vector()
        # New position in space, before accounting for gravity.
        dx, dy, dz = dx * d, dy * d, dz * d
        # gravity
        if not self.flying:
            # Update your vertical speed: if you are falling, speed up until you
            # hit terminal velocity; if you are jumping, slow down until you
            # start falling.
            self.dy -= dt * GRAVITY
            self.dy = max(self.dy, -TERMINAL_VELOCITY)
            dy += self.dy * dt
        # collisions
        old_pos = self.position
        x, y, z = old_pos
        x, y, z = self.collide((x + dx, y + dy, z + dz), PLAYER_HEIGHT)
        self.position = (x, y, z)

        # Sptinting stuff. If the player stops moving in the x and z direction, the player stops sprinting
        # and the sprint fov is subtracted from the fov offset
        if old_pos[0]-self.position[0] == 0 and old_pos[2]-self.position[2] == 0:
            disablefov = False
            if self.sprinting:
                disablefov = True
            self.sprinting = False
            if disablefov:
                self.fov_offset -= SPRINT_FOV

    def collide(self, position, height):
        """ Checks to see if the player at the given `position` and `height`
        is colliding with any blocks in the world.
        Parameters
        ----------
        position : tuple of len 3
            The (x, y, z) position to check for collisions at.
        height : int or float
            The height of the player.
        Returns
        -------
        position : tuple of len 3
            The new position of the player taking into account collisions.
        """
        # How much overlap with a dimension of a surrounding block you need to
        # have to count as a collision. If 0, touching terrain at all counts as
        # a collision. If .49, you sink into the ground, as if walking through
        # tall grass. If >= .5, you'll fall through the ground.
        pad = 0.25
        p = list(position)
        np = normalize(position)
        self.collision_types = {"top":False,"bottom":False,"right":False,"left":False}
        for face in FACES:  # check all surrounding blocks
            for i in xrange(3):  # check each dimension independently
                if not face[i]:
                    continue
                # How much overlap you have with this dimension.
                d = (p[i] - np[i]) * face[i]
                if d < pad:
                    continue
                for dy in xrange(height):  # check each height
                    op = list(np)
                    op[1] -= dy
                    op[i] += face[i]
                    if np[1] < 1:
                        self.collision_types["top"] = True
                        self.dy = 1
                        break
                    if tuple(op) not in self.model.world:
                        continue
                    if self.model.world[tuple(op)] in THRU:
                        continue
                    p[i] -= (d - pad) * face[i]
                    # If you are colliding with the ground or ceiling, stop
                    # falling / rising.
                    if face == (0, -1, 0):
                        self.collision_types["top"] = True
                        self.dy = 0
                    if face == (0, 1, 0):
                        self.collision_types["bottom"] = True
                        self.dy = 0
                    break
        return tuple(p)

    def on_mouse_press(self, x, y, button, modifiers):
        """ Called when a mouse button is pressed. See pyglet docs for button
        amd modifier mappings.
        Parameters
        ----------
        x, y : int
            The coordinates of the mouse click. Always center of the screen if
            the mouse is captured.
        button : int
            Number representing mouse button that was clicked. 1 = left button,
            4 = right button.
        modifiers : int
            Number representing any modifying keys that were pressed when the
            mouse button was clicked.
        """
        if self.exclusive:
            vector = self.get_sight_vector()
            block, previous = self.model.hit_test(self.position, vector)
            if (button == mouse.RIGHT) or \
                    ((button == mouse.LEFT) and (modifiers & key.MOD_CTRL)):
                # ON OSX, control + left click = right click.
                bid = self.model.world[block]
                if bid in REPLACE:
                    self.model.remove_block(block)
                    self.model.add_block(block, self.block)
                elif bid == "tnt":
                    bx, by, bz = block
                    for tx in xrange(-4,4):
                        for ty in xrange(-4,4):
                            for tz in xrange(-4,4):
                                poss = (bx + tx, by + ty, bz + tz)
                                if poss in self.model.world and self.model.world[poss] not in TNTRESIST:
                                    self.model.remove_block(poss)
                else:
                    if previous:
                        if self.block == "sponge":
                            bx, by, bz = block
                            abso = False
                            for tx in xrange(-4,4):
                                for ty in xrange(-4,4):
                                    for tz in xrange(-4,4):
                                        poss = (bx + tx, by + ty, bz + tz)
                                        if poss in self.model.world and self.model.world[poss] == "water":
                                            self.model.remove_block(poss)
                                            abso = True
                            if abso == True:
                                self.model.add_block(previous, "wet_sponge")
                            else:
                                self.model.add_block(previous, self.block)
                        else:
                            self.model.add_block(previous, self.block)
            elif button == pyglet.window.mouse.LEFT and block:
                bid = self.model.world[block]
                self.model.remove_block(block)
        else:
            self.set_exclusive_mouse(True)

    def on_mouse_motion(self, x, y, dx, dy):
        """ Called when the player moves the mouse.
        Parameters
        ----------
        x, y : int
            The coordinates of the mouse click. Always center of the screen if
            the mouse is captured.
        dx, dy : float
            The movement of the mouse.
        """
        if self.exclusive:
            m = 0.15
            x, y = self.rotation
            x, y = x + dx * m, y + dy * m
            y = max(-90, min(90, y))
            self.rotation = (x, y)

    def on_mouse_scroll(self, x, y, scroll_x, scroll_y):
        if scroll_y == -1:
            if self.bindx==0:
                self.bindx=len(self.inventory)-1
            else:
                self.bindx-=1
            self.block=self.inventory[self.bindx]
        elif scroll_y == 1:
            if self.bindx==len(self.inventory)-1:
                self.bindx=0
            else:
                self.bindx+=1
            self.block=self.inventory[self.bindx]

    def on_key_press(self, symbol, modifiers):
        """ Called when the player presses a key. See pyglet docs for key
        mappings.
        Parameters
        ----------
        symbol : int
            Number representing the key that was pressed.
        modifiers : int
            Number representing any modifying keys that were pressed.
        """
        if symbol == key.W:
            self.strafe[0] -= 1
        elif symbol == key.S:
            self.strafe[0] += 1
        elif symbol == key.A:
            self.strafe[1] -= 1
        elif symbol == key.D:
            self.strafe[1] += 1
        elif symbol == key.C:
            self.fov_offset -= 60.0
        elif symbol == key.SPACE:
            self.jumping = True
        elif symbol == key.ESCAPE:
            self.set_exclusive_mouse(False)
        elif symbol == key.LSHIFT:
            self.crouch = True
            if self.sprinting:
                self.fov_offset -= SPRINT_FOV
                self.sprinting = False
        elif symbol == key.R:
            if not self.crouch:
                if not self.sprinting:
                    self.fov_offset += SPRINT_FOV
                self.sprinting = True
        elif symbol == key.TAB:
            self.flying = not self.flying
        elif symbol in self.num_keys:
            self.bindx = (symbol - self.num_keys[0]) % len(self.inventory)
            self.block = self.inventory[self.bindx]
        elif symbol == key.F:
            if self.bindx==0:
                self.bindx=len(self.inventory)-1
            else:
                self.bindx-=1
            self.block=self.inventory[self.bindx]
        elif symbol == key.G:
            if self.bindx==len(self.inventory)-1:
                self.bindx=0
            else:
                self.bindx+=1
            self.block=self.inventory[self.bindx]
            

    def on_key_release(self, symbol, modifiers):
        """ Called when the player releases a key. See pyglet docs for key
        mappings.
        Parameters
        ----------
        symbol : int
            Number representing the key that was pressed.
        modifiers : int
            Number representing any modifying keys that were pressed.
        """
        if symbol == key.W:
            self.strafe[0] += 1
        elif symbol == key.S:
            self.strafe[0] -= 1
        elif symbol == key.A:
            self.strafe[1] += 1
        elif symbol == key.D:
            self.strafe[1] -= 1
        elif symbol == key.SPACE:
            self.jumping = False
        elif symbol == key.LSHIFT:
            self.crouch = False
        elif symbol == key.C:
            self.fov_offset += 60.0

    def on_resize(self, width, height):
        """ Called when the window is resized to a new `width` and `height`.
        """
        # label
        self.label.y = height - 10
        # reticle
        if self.reticle:
            self.reticle.delete()
        x, y = self.width // 2, self.height // 2
        n = 10
        self.reticle = pyglet.graphics.vertex_list(4,
            ('v2i', (x - n, y, x + n, y, x, y - n, x, y + n))
        )

    def set_2d(self):
        """ Configure OpenGL to draw in 2d.
        """
        width, height = self.get_size()
        glDisable(GL_DEPTH_TEST)
        viewport = self.get_viewport_size()
        glViewport(0, 0, max(1, viewport[0]), max(1, viewport[1]))
        glMatrixMode(GL_PROJECTION)
        glLoadIdentity()
        glOrtho(0, max(1, width), 0, max(1, height), -1, 1)
        glMatrixMode(GL_MODELVIEW)
        glLoadIdentity()

    def set_3d(self):
        """ Configure OpenGL to draw in 3d.
        """
        width, height = self.get_size()
        glEnable(GL_DEPTH_TEST)
        viewport = self.get_viewport_size()
        glViewport(0, 0, max(1, viewport[0]), max(1, viewport[1]))
        glMatrixMode(GL_PROJECTION)
        glLoadIdentity()
        gluPerspective(PLAYER_FOV + self.fov_offset, width / float(height), 0.1, 60.0)
        glMatrixMode(GL_MODELVIEW)
        glLoadIdentity()
        x, y = self.rotation
        glRotatef(x, 0, 1, 0)
        glRotatef(-y, math.cos(math.radians(x)), 0, math.sin(math.radians(x)))
        x, y, z = self.position
        if self.crouch:
            glTranslatef(-x, -y+0.2, -z)
        else:
            glTranslatef(-x, -y, -z)

    def on_draw(self):
        """ Called by pyglet to draw the canvas.
        """
        self.clear()
        self.set_3d()
        glColor3d(1, 1, 1)
        self.model.batch.draw()
        #blending????
        glEnable(GL_BLEND)
        self.model.batch2.draw()
        glDisable(GL_BLEND)
        
        self.draw_focused_block()
        self.set_2d()
        self.draw_label()
        self.draw_blabel()
        self.draw_reticle()

    def draw_focused_block(self):
        """ Draw black edges around the block that is currently under the
        crosshairs.
        """
        vector = self.get_sight_vector()
        block = self.model.hit_test(self.position, vector)[0]
        if block:
            x, y, z = block
            vertex_data = cube_vertices(x, y, z, 0.51)
            glColor3d(0, 0, 0)
            glPolygonMode(GL_FRONT_AND_BACK, GL_LINE)
            pyglet.graphics.draw(24, GL_QUADS, ('v3f/static', vertex_data))
            glPolygonMode(GL_FRONT_AND_BACK, GL_FILL)

    def draw_label(self):
        """ Draw the label in the top left of the screen.
        """
        x, y, z = self.position
        self.label.text = '%02d (%.2f, %.2f, %.2f) %d / %d' % (
            pyglet.clock.get_fps(), x, y, z,
            len(self.model._shown), len(self.model.world))
        self.label.draw()

    def draw_blabel(self):
        """ Draw the label in the top left of the screen.
        """
        x, y, z = self.position
        self.blabel.text = '<-F- %s -G->' % (
            self.invstr[self.bindx])
        self.blabel.draw()

    def draw_reticle(self):
        """ Draw the crosshairs in the center of the screen.
        """
        glColor3d(0, 0, 0)
        self.reticle.draw(GL_LINES)


def setup_fog():
    """ Configure the OpenGL fog properties.
    """
    # Enable fog. Fog "blends a fog color with each rasterized pixel fragment's
    # post-texturing color."
    glEnable(GL_FOG)
    # Set the fog color.
    glFogfv(GL_FOG_COLOR, (GLfloat * 4)(0.5, 0.69, 1.0, 1))
    # Say we have no preference between rendering speed and quality.
    glHint(GL_FOG_HINT, GL_DONT_CARE)
    # Specify the equation used to compute the blending factor.
    glFogi(GL_FOG_MODE, GL_LINEAR)
    # How close and far away fog starts and ends. The closer the start and end,
    # the denser the fog in the fog range.
    glFogf(GL_FOG_START, 40.0)
    glFogf(GL_FOG_END, 60.0)


def setup():
    """ Basic OpenGL configuration.
    """
    # Set the color of "clear", i.e. the sky, in rgba.
    glClearColor(0.5, 0.69, 1.0, 1)
    # Enable culling (not rendering) of back-facing facets -- facets that aren't
    # visible to you.
    glEnable(GL_CULL_FACE)
    # Enable Alpha for cutout transparency
    glEnable(GL_ALPHA_TEST)
    glAlphaFunc(GL_GREATER, .1)
    # Set the texture minification/magnification function to GL_NEAREST (nearest
    # in Manhattan distance) to the specified texture coordinates. GL_NEAREST
    # "is generally faster than GL_LINEAR, but it can produce textured images
    # with sharper edges because the transition between texture elements is not
    # as smooth."
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_NEAREST)
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_NEAREST)
    setup_fog()


def main():
    splashtext_list = ["Deja vu.", "KABOOM!!!", "Dehydration station!", "Opaque water.", "Funky sand", "OH NO NOT THE BEES!", "kurtis likes wood", "nice",
                       "more moddable than minecraft", "funni title", "man", "i may be stupid", "glEnable(GL_BLEND)", "eef freef", "I'm in a nailt in brurg",
                       "More text than ever!!", "this code won't work.", "Deja vu."]
    Splash_text = splashtext_list[random.randint(0,len(splashtext_list)-1)]
    window = Window(width=1280, height=720, caption='pyCraft - '+ Splash_text, resizable=True)
    # Hide the mouse cursor and prevent the mouse from leaving the window.
    window.set_exclusive_mouse(True)
    setup()
    pyglet.app.run()

main()
