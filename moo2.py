"""This module is a MOO2 saved game reader and editor."""

import array, mmap, itertools, random

# The offsets into the saved game file.
starblock_offset, planetblock_offset = 0x17ad3, 0x162e9

class Game(object):
    def __init__(self, path):
        """Construct a game given a path to a saved game file."""
        self.path = path
        # Read in the file at the given path.
        f = open(path, 'rb')
        self.data = array.array('B', f.read())
        f.close()
        # Find higher number planet.
        self.maxplanet=max(p.number for s in self.stars() for p in s.planets())

    def save(self, path=None):
        """Save to the given path, or the original path if no path is given."""
        filepath = path if path else self.path
        f = open(filepath, 'wb')
        strdata = ''.join(chr(i) for i in self.data)
        f.write(strdata)
        f.close()

    def stars(self):
        for i in xrange(Star.max_stars):
            star = Star(self, i)
            if not star.exists: break
            yield star

    def star(self, name):
        """Return a star with a specified name, None if it doesn't exist."""
        for s in self.stars():
            if s.name==name:
                return s

    def _getnumplayers(self):
        """The number of players."""
        return self.data[0x1aa0c]
    numplayers = property(_getnumplayers)

    def players(self):
        for i in xrange(self.numplayers):
            yield Player(self, i)

    def short_at_offset(self, o):
        return self.data[o] + (self.data[o+1]<<8)
    def set_short_at_offset(self, o, value):
        self.data[o+1] = value>>8
        self.data[o] = value&0xff

class DataOffsetType(object):
    def _getblock_str(self):
        """A string representation of the data block of this planet."""
        return ' '.join('%02X' % b for b in self.game.data[
            self.offset:self.offset+self.block_size])
    block_str = property(_getblock_str, None, None, _getblock_str.__doc__)

class Star(DataOffsetType):
    """Encapsulation of the data for a given star."""
    # The amount of the offset into the file where the stars start to appear.
    block_offset = 0x17ad3
    # The maximum number of stars that a saved game file can support.
    max_stars = 72
    # The number of bytes for each star.
    block_size = 0x71
    # The offset into the star block where the planets are indexed.
    planet_offset = 0x4a

    # Star color indices.
    star_color = ['blue', 'white', 'yellow', 'orange', 'red']
    
    def __init__(self, game, number):
        # Check bounds.
        if number < 0 or number >= Star.max_stars:
            raise ValueError("star number must be in range 0 to %d"%(
                Star.max_stars-1))
        self.offset = Star.block_offset + number*Star.block_size
        self.number = number
        self.game = game

    def _getexists(self):
        """True if the given star exists in the game."""
        return bool(self.game.data[self.offset])
    exists = property(_getexists, None, None, _getexists.__doc__)

    def _getname(self):
        """The name of the star."""
        end = self.offset
        d = self.game.data
        while d[end]: end+=1
        return ''.join(chr(c) for c in d[self.offset:end])
    name = property(_getname, None, None, _getname.__doc__)

    # X AND Y COORDINATES ON THE STAR MAP

    def _getx(self):
        """The x-coordinate of the star."""
        return self.game.short_at_offset(self.offset+15)
    def _setx(self, value):
        self.game.set_short_at_offset(self.offset+15, value)
    x = property(_getx, _setx, None, _getx.__doc__)

    def _gety(self):
        """The y-coordinate of the star."""
        return self.game.short_at_offset(self.offset+17)
    def _sety(self, value):
        self.game.set_short_at_offset(self.offset+17, value)
    y = property(_gety, _sety, None, _gety.__doc__)

    def distance(self, star):
        """The square of the distance of this star to another star."""
        dx = self.x - star.x
        dy = self.y - star.y
        return dx*dx + dy*dy

    def __str__(self):
        """A string representation of this star."""
        return '<star 0x%02X %s>'%(self.number,self.name)

    # The data block.

    def _getblock(self):
        return self.game.data[self.offset:self.offset+Star.block_size]
    block = property(_getblock, None, None, _getblock.__doc__)

    def _getblock_str(self):
        """A string representation of the data block of this star."""
        return ' '.join('%02X'%b for b in self.game.data[
            self.offset:self.offset+Star.block_size])
    block_str = property(_getblock_str, None, None, _getblock_str.__doc__)

    def planets(self):
        """Iterator over the planets in the star system."""
        d = self.game.data
        for i in xrange(self.planet_offset, self.planet_offset+10, 2):
            planet_num = self.game.short_at_offset(self.offset+i)
            if planet_num == 0xffff: continue
            yield Planet(self.game, planet_num)

    def planet_at(self, pos):
        """The planet at orbital position 0 through 4.

        This returns None if there is no planet at that position"""
        if not 0<=pos<=4:
            raise IndexError("planets indexed 0 through 4")
        planet_num = self.game.short_at_offset(
            self.offset+self.planet_offset+2*pos)
        return None if planet_num == 0xffff else Planet(self.game, planet_num)

    def make_planet(self, pos, btype=3):
        """Makes a new planet at the indicated position.

        The btype argument indicates the type of body (planet,
        asteroid, gas-giant) and follows the same convention as the
        Planet.type member.  If left on the default as a planet
        (type=3), then the planet is the same as is created when an
        asteroid field is subjected to the 'artificial planet'
        construction (large, abundant, normal-G, barren).  If a planet
        exists there, an exception will be raised.  This function
        returns the constructed planet."""
        if self.planet_at(pos) != None:
            raise ValueError("planet already exists at position %d" % pos)
        if not 1<=btype<=3:
            raise ValueError("type must be 1 through 3")
        self.game.maxplanet += 1
        newp = Planet(self.game, self.game.maxplanet)
        newdata = array.array('B', [0]*Planet.block_size)
        # No colony yet, set this to 0xffff.
        newdata[0] = newdata[1] = 0xff
        # Star system number and position, and that this is a planet.
        newdata[2], newdata[3], newdata[4] = self.number, pos, btype
        # A large, medium gravity barren world.
        newdata[5], newdata[6], newdata[8] = 3, 1, 2
        # Unpredictably (to the user) but deterministically assign scenery.
        newdata[9] = random.Random(pos + btype*5 + self.number*15).randrange(3)
        # Abundant world, assign "7" for large.
        newdata[0xa], newdata[0xd] = 2, Planet.size2blockd[newdata[5]]
        # Put in the planet data.
        self.game.data[newp.offset : newp.offset+Planet.block_size] = newdata
        # Point the star to the appropriate planet data.
        self.game.set_short_at_offset(
            self.offset+self.planet_offset+2*pos, newp.number)
        # Return the planet.
        return newp

class Player(DataOffsetType):
    """A representation of players."""
    # Offset and block size.
    block_offset, block_size = 0x1aa0f, 0xea9
    max_players = 8
    # Offsets of common data.  The names are rather interesting.  In
    # the file, they appear to have 0x14 bytes set aside for them, but
    # in the game they must be at most 14 bytes long.  An interesting
    # artifact of programmer getting confused between hex and decimal?
    leader_name_offset, leader_name_size = 0x0, 14
    race_name_offset, race_name_size = 0x14, 14

    def __init__(self, game, number):
        if number<0 or number>=game.numplayers:
            raise ValueError(
                "player number be nonnegative and less than number of players")
        self.offset = Player.block_offset + number*Player.block_size
        self.number = number
        self.game = game

    def _getleadername(self):
        """The name of the leader."""
        chars = []
        d = self.game.data
        for i in xrange(self.leader_name_size):
            c = d[self.offset+self.leader_name_offset+i]
            if not c: break
            chars.append(chr(c))
        return ''.join(chars)
    leader_name = property(_getleadername)

    def _getracename(self):
        """The name of the race."""
        chars = []
        d = self.game.data
        for i in xrange(self.race_name_size):
            c = d[self.offset+self.race_name_offset+i]
            if not c: break
            chars.append(chr(c))
        return ''.join(chars)
    race_name = property(_getracename)

    def __str__(self):
        """A string representation of this player."""
        return '<player 0x%02X %s (%s)>'%(
            self.number,self.race_name, self.leader_name)

class Colony(DataOffsetType):
    """A representation of colonies."""
    # The amount of the offset into the file where colonies start to appear.
    block_offset = 0x25d
    # The maximum number of colonies that a saved game file can
    # support.  Strangely this is considerably less than the maximum
    # number of planets, which is surprising since, in principle, any
    # planet should be able to be colonized.
    max_colonies = 360
    # The size of the blocks for each colony.
    block_size = 0x169

    def __init__(self, game, number):
        if number < 0 or number >= self.max_colonies:
            raise ValueError("colony number must be in range 0 to %d"%(
                Colony.max_colonies))
        self.offset = Colony.block_offset + number*Colony.block_size
        self.number = number
        self.game = game

    def _getplanet(self):
        """The planet this colony is on."""
        planetnum = self.game.short_at_offset(self.offset+2)
        return Planet(self.game, planetnum) if planetnum != 0xffff else None
    planet = property(_getplanet)

    def _getplayer(self):
        """The player this colony belongs to."""
        pnum = self.game.data[self.offset+0x0]
        return Player(self.game, pnum) if pnum != 0xff else None
    player = property(_getplayer)

class Planet(DataOffsetType):
    """A representation of all planets in the system."""
    # The amount of the offset into the file where planets start to appear.
    block_offset = 0x162e9
    # The maximum number of planets that a saved game file can
    # support.  Crucially, this number is five times the maximum
    # number of stars.
    max_planets = 360
    # Mapping of type of body code to description.
    type2desc = {1:'asteroid', 2:'gas giant', 3:'planet'}
    # Mapping of planet terraform to description.
    terraform2desc = ['toxic', 'radiated', 'barren', 'desert', 'tundra',
                      'ocean', 'swamp', 'arid', 'terran', 'gaia']
    # Mapping of planet terraform to the typical food.
    terraform2food = [0, 0, 0, 1, 1, 2, 2, 1, 2, 3]
    # Mapping of planet size code to the size description.
    size2desc = ['tiny', 'small', 'medium', 'large', 'huge']
    # Mapping of planet size code to the *typical* byte in 0xd.
    size2blockd = [2, 4, 5, 7, 10]
    # Mapping of planet gravity to the gravity description.
    gravity2desc = ['LG', 'NG', 'HG']
    # Mapping of planet richness to the richness description.
    richness2desc = ['ultra poor', 'poor', 'abundant', 'rich', 'ultra rich']
    # Within the block, where are these things stored?
    block_size = 0x11

    def __init__(self, game, number):
        if number < 0 or number >= self.max_planets:
            raise ValueError("planet number must be in range 0 to %d"%(
                Planet.max_planets))
        self.offset = Planet.block_offset + number*Planet.block_size
        self.number = number
        self.game = game

    def _getcolonynum(self):
        """The index of the colony on this planet, or None if there is none."""
        colony_index = self.game.short_at_offset(self.offset)
        return None if colony_index == 0xffff else colony_index
    colonynum = property(_getcolonynum)

    def _getcolony(self):
        """The colony on this planet, or None if there is none."""
        num = self.colonynum
        if num==None: return None
        return Colony(self.game, num)
    colony = property(_getcolony)

    def _getstarnum(self):
        """The number of the star containing this planet."""
        return self.game.data[self.offset+2]
    starnum = property(_getstarnum)

    def _getstar(self):
        """The star containing this planet."""
        return Star(self.game, self.starnum)
    star = property(_getstar, None, None, _getstar.__doc__)

    def _getposition(self):
        """The planet's position to its star, with 0 closest, 4 furthest.

        Note that in setting this attribute, if you set this planet to
        the position where another planet exists, then their positions
        will be swapped in the star."""
        return self.game.data[self.offset+3]
    def _setposition(self, pos):
        # The only annoying part is the potential for planet placement swaps.
        other = self.star.planet_at(pos)
        # Get our current position.
        oldpos = self.position
        if pos==oldpos: return
        if other:
            # We do need to swap positions.  First swap planet positions.
            self.game.data[other.offset+3], self.game.data[self.offset+3] = \
                                            self.position, other.position
        else:
            # No other planet, no need to swap positions in the planet data.
            self.game.data[self.offset+3] = pos
        # Then swap planet positions as stored in the star.  We have
        # to do this even when there is no planet, as we need the
        # "blank" spot to have 0xffff.
        aoffset = self.star.offset+Star.planet_offset+2*pos
        boffset = self.star.offset+Star.planet_offset+2*oldpos
        d = self.game.data
        d[aoffset], d[aoffset+1], d[boffset], d[boffset+1] = (
            d[boffset], d[boffset+1], d[aoffset], d[aoffset+1])
    position = property(_getposition, _setposition, None, _getposition.__doc__)

    # TYPE

    def _gettype(self):
        """The code of the type of body, 1, 2, 3, or undefined non-existant.

        1 is an asteroid, 2 is a gas giant, and 3 is a planet."""
        return self.game.data[self.offset+4]
    def _settype(self, value):
        if value not in Planet.type2desc:
            raise ValueError("type code must be one of %s"%(
                ','.join('%d'%t for t in Planet.type2desc)))
        self.game.data[self.offset+4] = value
    type = property(_gettype, _settype, None, _gettype.__doc__)

    def _gettype_str(self):
        """The string of the type of body (asteroid, gas gaint, planet)."""
        return Planet.type2desc.get(self.type, None)
    def _settype_str(self, value):
        self.type = dict((v,k) for k,v in Planet.type2desc.items())[value]
    type_str = property(_gettype_str, _settype_str, None, _gettype_str.__doc__)
        
    type = property(_gettype, None, None, _gettype.__doc__)

    # TERRAFORM

    def _getterraform(self):
        """Terraform code, 0 through 9, or undefined if non-existant.

        Setting this quantity will may also change the base food of
        this planet."""
        tercode = self.game.data[self.offset+8]
        return tercode
    def _setterraform(self, value):
        if not 0<=value<len(Planet.terraform2desc):
            raise ValueError("terraformcode must be in range 0 to %d"%(
                len(Planet.terraform2desc)-1))
        self.food += self.terraform2food[value] - \
                     self.terraform2food[self.terraform]
        self.game.data[self.offset+8] = value
    terraform = property(_getterraform, _setterraform,
                         None, _getterraform.__doc__)

    def _getterraform_str(self):
        """The string for the terraforming of the body."""
        return Planet.terraform2desc[self.terraform]
    def _setterraform_str(self, value):
        try:
            self.terraform = Planet.terraform2desc.index(value)
        except ValueError:
            raise ValueError("terraform_str must be one of %s"%(
                ','.join(Planet.terraform2desc)))
    terraform_str = property(_getterraform_str, _setterraform_str,
                             None, _getterraform_str.__doc__)

    # SIZE
    
    def _getsize(self):
        """The size of the body, where 0 is tiny, and 4 is huge."""
        return self.game.data[self.offset+5]
    def _setsize(self, value):
        if value < 0 or value > 4:
            raise ValueError("size must be between 0 and 4 inclusive")
        oldsize = self.size
        self.game.data[self.offset+5] = value
        # If block D is correlated with size, then change this too.
        # If it's decorrelated, do not bother.
        if self.game.data[self.offset+0xd]==self.size2blockd[oldsize]:
            self.game.data[self.offset+0xd]=self.size2blockd[value]
    size = property(_getsize, _setsize, None, _getsize.__doc__)

    def _getsize_str(self):
        """The size of the body as a string."""
        try:
            return Planet.size2desc[self.size]
        except IndexError:
            return None
    def _setsize_str(self, value):
        try:
            self.size = Planet.size2desc.index(value)
        except ValueError:
            raise ValueError("size_str must be one of %s"%(
                ','.join(Planet.size2desc)))
    size_str = property(_getsize_str, _setsize_str, None, _getsize_str.__doc__)

    # FOOD
    
    def _getfood(self):
        """The base food of the body, where 0 is none.

        Base food is an interesting quantity as it is affected by many
        factors: the terraforming of the object, the owner if they
        have a farming bonus, the presence of soil enrichment or
        weather control, etc."""
        return self.game.data[self.offset+11]
    def _setfood(self, value):
        if value < 0 or value > 255:
            raise ValueError("food must be between 0 and 255 inclusive")
        self.game.data[self.offset+11] = value
    food = property(_getfood, _setfood, None, _getfood.__doc__)

    # GRAVITY
        
    def _getgravity(self):
        """The gravity code, where 0 is low, 1 medium, and 2 high gravity."""
        return self.game.data[self.offset+6]
    def _setgravity(self, value):
        if not 0<=value<=4:
            raise ValueError("gravity must be between 0 and 4 inclusive")
        self.game.data[self.offset+6] = value
    gravity = property(_getgravity, _setgravity, None, _getgravity.__doc__)

    def _getgravity_str(self):
        """The gravity of the body as a string."""
        try:
            return Planet.gravity2desc[self.gravity]
        except IndexError:
            return None
    def _setgravity_str(self, value):
        try:
            self.gravity = Planet.gravity2desc.index(value)
        except ValueError:
            raise ValueError("gravity_str must be one of %s"%(
                ','.join(Planet.gravity2desc)))
    gravity_str = property(_getgravity_str, _setgravity_str,
                           None, _getgravity_str.__doc__)

    # RICHNESS

    def _getrichness(self):
        """The richness of the body, with 0 ultra poor, 4 ultra rich."""
        return self.game.data[self.offset+0xa]
    def _setrichness(self, value):
        if not 0<=value<=4:
            raise ValueError("richness must be between 0 and 4 inclusive")
        self.game.data[self.offset+0xa] = value
    richness = property(_getrichness, _setrichness, None, _getrichness.__doc__)

    def _getrichness_str(self):
        """The richness of the body as a string."""
        try:
            return Planet.richness2desc[self.richness]
        except IndexError:
            return None
    def _setrichness_str(self, value):
        try:
            self.richness = Planet.richness2desc.index(value)
        except ValueError:
            raise ValueError("richness_str must be one of %s"%(
                ','.join(Planet.richness2desc)))
    richness_str = property(_getrichness_str, _setrichness_str,
                            None, _getrichness_str.__doc__)

    def __str__(self):
        tokens = ['planet-%03d' % (self.number)]
        if self.type_str=='planet':
            tokens.extend((self.size_str, self.richness_str,
                           self.terraform_str))
            if self.gravity != 1: tokens.append(self.gravity_str)
        else:
            tokens.append(self.type_str)
        return '<'+' '.join(tokens)+'>'

    # SCENERY

    def _getscenery(self):
        """The scenery of the planet in colony view (either 0, 1, or 2)."""
        return self.game.data[self.offset+0x9]
    def _setscenery(self, value):
        if not 0<=value<=2:
            raise ValueError("scenery must be between 0 and 2 inclusive")
        self.game.data[self.offset+0x9] = value
    scenery = property(_getscenery, _setscenery)

if __name__ == '__main__':
    def count(i):
        c = {}
        for j in i: c[j] = c.get(j,0) + 1
        return c

    def idealize(starsystem):
        # Make the star system better.
        for p in starsystem.planets():
            p.richness = max(
                p.richness, 3 if p.colony else random.randint(2,4))
            p.size = max(p.size, 3)
            if p.size + p.richness > 5 and not p.colony:
                p.gravity = random.randint(1,2)
            if p.terraform == 0:
                p.terraform = 1
        # Fill in the remainder with planets.
        used_positions = set(p.position for p in starsystem.planets())
        for pos in xrange(5):
            if pos in used_positions:
                continue
            p = starsystem.make_planet(pos)
            p.size = random.randint(3,4)
            p.richness = random.randint(2,4)
            if p.size + p.richness > 5:
                p.gravity = random.randint(1,2)
            p.terraform = random.randint(1,7)

    def orionize():
        starsystem = g.star('Orion')
        used_positions = set(p.position for p in starsystem.planets())
        for pos in xrange(5):
            if pos not in used_positions:
                p = starsystem.make_planet(pos, 1)
    
    import sys
    gameno = int(sys.argv[1]) if len(sys.argv)>=2 else 4
    p = '/Users/thomas/Documents/DosBox/CDrive/Moo2/MPS/ORION2/SAVE%d.GAM' % (
        gameno)
    print 'Reading game number %d' % gameno
    g = Game(p)

    for p in g.players():
        print p

    cry = g.star('Cryslon')
    idealize(cry)
    orionize()
