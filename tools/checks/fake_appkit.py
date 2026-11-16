"""Fake objc, AppKit, Foundation and ScreenSaver modules for tools/checks/check_mac_options.py.

install() puts them in sys.modules so mac_options and mac_saver import on
Windows. Each fake class has only the selectors the Mac code is expected to
call, and records what it is given (frame, enabled, hidden, title, items,
value, target, action), so a call the fakes lack fails with AttributeError.
They check our calls against our own reading of the AppKit API: a selector
that is wrong on a real Mac but present here still passes. Only the manual
test (design/mac-options-test.md) settles that.
"""

import sys
import types


# Geometry
class _Size:
    def __init__(self, w, h):
        self.width, self.height = w, h


class _Point:
    def __init__(self, x, y):
        self.x, self.y = x, y


class Rect:
    def __init__(self, x, y, w, h):
        self.origin = _Point(x, y)
        self.size = _Size(w, h)

    def __repr__(self):
        return f"Rect({self.origin.x}, {self.origin.y}, {self.size.width}, {self.size.height})"


def NSMakeRect(x, y, w, h):
    return Rect(x, y, w, h)


def NSRectFill(_rect):
    pass


# Objects
class NSObject:
    @classmethod
    def alloc(cls):
        return cls()

    def init(self):
        return self


class NSView(NSObject):
    def __init__(self):
        self._frame = Rect(0, 0, 0, 0)
        self._hidden = False
        self._subviews = []
        self._superview = None
        self._window = None  # set on a window's content view only
        self._layer = None  # a fake Layer when the test makes the view layer-backed
        self.autoresizing = 0

    def initWithFrame_(self, rect):
        self._frame = rect
        return self

    def setToolTip_(self, text):
        self._tooltip = text

    def frame(self):
        return self._frame

    def setFrame_(self, rect):
        self._frame = rect

    def bounds(self):
        return Rect(0, 0, self._frame.size.width, self._frame.size.height)

    def addSubview_(self, view):
        view._superview = self
        self._subviews.append(view)

    def subviews(self):
        return list(self._subviews)

    def superview(self):
        return self._superview

    def window(self):
        v = self
        while v is not None:
            if v._window is not None:
                return v._window
            v = v._superview
        return None

    def setHidden_(self, flag):
        self._hidden = bool(flag)

    def isHidden(self):
        return self._hidden

    def setAutoresizingMask_(self, mask):
        self.autoresizing = mask

    def layer(self):
        return self._layer

    def descendants(self):
        """Fake-only: every view below this one, including scroll document views."""
        out = []
        for v in self._subviews:
            out.append(v)
            out += v.descendants()
        return out


class NSControl(NSView):
    def __init__(self):
        super().__init__()
        self._enabled = True
        self._tag = 0
        self._target = None
        self._action = None
        self.font = None

    def setEnabled_(self, flag):
        self._enabled = bool(flag)

    def isEnabled(self):
        return self._enabled

    def setTag_(self, tag):
        self._tag = int(tag)

    def tag(self):
        return self._tag

    def setTarget_(self, target):
        self._target = target

    def target(self):
        return self._target

    def setAction_(self, action):
        self._action = action

    def action(self):
        return self._action

    def setFont_(self, font):
        self.font = font

    def fire(self):
        """Fake-only: what a click does, the action sent to the target."""
        getattr(self._target, self._action.replace(":", "_"))(self)


class NSTextField(NSControl):
    def __init__(self):
        super().__init__()
        self._string = ""
        self._delegate = None
        self.editable = True
        self.selectable = True
        self.text_color = None
        self.alignment = None
        self.max_layout_width = None

    @classmethod
    def wrappingLabelWithString_(cls, text):
        f = cls()
        f._string = str(text)
        f.editable = False
        return f

    def stringValue(self):
        return self._string

    def setStringValue_(self, text):
        self._string = str(text)

    def setEditable_(self, flag):
        self.editable = bool(flag)

    def setSelectable_(self, flag):
        self.selectable = bool(flag)

    def setDelegate_(self, delegate):
        self._delegate = delegate

    def delegate(self):
        return self._delegate

    def setTextColor_(self, color):
        self.text_color = color

    def setAlignment_(self, alignment):
        self.alignment = alignment

    def setPreferredMaxLayoutWidth_(self, width):
        self.max_layout_width = width

    def type_text(self, text):
        """Fake-only: typing, then the delegate's controlTextDidChange:."""
        self._string = text
        self._delegate.controlTextDidChange_(_Note("NSControlTextDidChangeNotification", self))


class NSButton(NSControl):
    def __init__(self):
        super().__init__()
        self._title = ""
        self._state = 0
        self.button_type = None
        self.key_equivalent = ""

    @classmethod
    def buttonWithTitle_target_action_(cls, title, target, action):
        b = cls()
        b._title, b._target, b._action = title, target, action
        return b

    def setButtonType_(self, kind):
        self.button_type = kind

    def setTitle_(self, title):
        self._title = title

    def title(self):
        return self._title

    def setState_(self, state):
        self._state = int(state)

    def state(self):
        return self._state

    def setKeyEquivalent_(self, key):
        self.key_equivalent = key


class NSSlider(NSControl):
    def __init__(self):
        super().__init__()
        self.min = 0.0
        self.max = 1.0
        self.continuous = False
        self._value = 0.0

    def setMinValue_(self, v):
        self.min = float(v)

    def setMaxValue_(self, v):
        self.max = float(v)

    def setContinuous_(self, flag):
        self.continuous = bool(flag)

    def setDoubleValue_(self, v):
        self._value = min(self.max, max(self.min, float(v)))

    def doubleValue(self):
        return self._value


class NSPopUpButton(NSControl):
    def __init__(self):
        super().__init__()
        self.items = []
        self._selected = -1
        self.pulls_down = None

    def initWithFrame_pullsDown_(self, rect, pulls_down):
        self._frame = rect
        self.pulls_down = pulls_down
        return self

    def addItemsWithTitles_(self, titles):
        self.items += list(titles)
        if self._selected < 0 and self.items:
            self._selected = 0

    def selectItemAtIndex_(self, i):
        self._selected = int(i)

    def indexOfSelectedItem(self):
        return self._selected


class NSSegmentedControl(NSControl):
    def __init__(self):
        super().__init__()
        self.labels = []
        self._selected = -1
        self.tracking = None

    def setSegmentCount_(self, n):
        self.labels = [""] * int(n)

    def setLabel_forSegment_(self, label, i):
        self.labels[i] = label

    def setTrackingMode_(self, mode):
        self.tracking = mode

    def setSelectedSegment_(self, i):
        self._selected = int(i)

    def selectedSegment(self):
        return self._selected


class NSBox(NSView):
    def __init__(self):
        super().__init__()
        self._title = ""

    def setTitle_(self, title):
        self._title = title

    def title(self):
        return self._title


class NSScrollView(NSView):
    def __init__(self):
        super().__init__()
        self._doc = None
        self.vertical = False

    def setHasVerticalScroller_(self, flag):
        self.vertical = bool(flag)

    def setDocumentView_(self, view):
        self._doc = view
        view._superview = self

    def documentView(self):
        return self._doc

    def descendants(self):
        return ([self._doc] + self._doc.descendants()) if self._doc is not None else []


class NSTabViewItem(NSObject):
    def __init__(self):
        self._ident = None
        self._label = ""
        self._view = None

    def initWithIdentifier_(self, ident):
        self._ident = ident
        return self

    def identifier(self):
        return self._ident

    def setLabel_(self, label):
        self._label = label

    def label(self):
        return self._label

    def setView_(self, view):
        self._view = view

    def view(self):
        return self._view


class NSTabView(NSView):
    def __init__(self):
        super().__init__()
        self.items = []
        self._delegate = None

    def addTabViewItem_(self, item):
        self.items.append(item)
        if item.view() is not None:
            item.view()._superview = self

    def tabViewItems(self):
        return list(self.items)

    def setDelegate_(self, delegate):
        self._delegate = delegate

    def delegate(self):
        return self._delegate

    def select(self, i):
        """Fake-only: a click on tab `i`, then the delegate's didSelect callback."""
        if self._delegate is not None:
            self._delegate.tabView_didSelectTabViewItem_(self, self.items[i])

    def descendants(self):
        out = super().descendants()
        for item in self.items:
            out += [item.view()] + item.view().descendants()
        return out


class NSWindow(NSObject):
    def __init__(self):
        self._content = NSView()
        self._content._window = self
        self._title = ""
        self.released_when_closed = True
        self.parent = None  # what sheetParent() returns; set by the test
        self.closed = 0
        self.ended = []  # windows passed to endSheet_
        self.style = None
        self.frames = []  # (rect, display, animate) given to setFrame_display_animate_
        self.color_spaces = []  # given to setColorSpace_
        self._screen = None  # what screen() returns; set by the test
        self._origin = (100, 100)

    TITLE_H = 28  # fake-only: frame height minus content height

    def initWithContentRect_styleMask_backing_defer_(self, rect, style, backing, defer):
        self._content._frame = rect
        self.style = style
        return self

    def frame(self):
        c = self._content._frame
        return Rect(*self._origin, c.size.width, c.size.height + self.TITLE_H)

    def setFrame_display_animate_(self, rect, display, animate):
        self.frames.append((rect, display, animate))
        self._origin = (rect.origin.x, rect.origin.y)
        self._content._frame = Rect(0, 0, rect.size.width, rect.size.height - self.TITLE_H)

    def setColorSpace_(self, space):
        self.color_spaces.append(space)

    def screen(self):
        return self._screen

    def contentView(self):
        return self._content

    def setTitle_(self, title):
        self._title = title

    def title(self):
        return self._title

    def setReleasedWhenClosed_(self, flag):
        self.released_when_closed = bool(flag)

    def sheetParent(self):
        return self.parent

    def endSheet_(self, win):
        self.ended.append(win)

    def close(self):
        self.closed += 1


class NSFont(NSObject):
    @classmethod
    def systemFontOfSize_(cls, size):
        return ("system", size)

    @classmethod
    def smallSystemFontSize(cls):
        return 11.0


class FakeFont:
    """A font with a family and NSFontManager trait bits (1 italic, 2 bold)."""

    def __init__(self, family, traits=0, size=13.0):
        self.family, self.traits, self.size = family, traits, size

    def pointSize(self):
        return self.size

    def familyName(self):
        return self.family


class NSFontManager(NSObject):
    _shared = None
    chosen = None  # fake-only: the font the font panel returns from convertFont_

    @classmethod
    def sharedFontManager(cls):
        if cls._shared is None:
            cls._shared = cls()
            cls._shared.selected = None
            cls._shared.target = None
            cls._shared.panel_opened = 0
        return cls._shared

    def setTarget_(self, target):
        self.target = target

    def setSelectedFont_isMultiple_(self, font, multiple):
        self.selected = font

    def selectedFont(self):
        return self.selected

    def fontWithFamily_traits_weight_size_(self, family, traits, weight, size):
        return FakeFont(family, traits, size)

    def orderFrontFontPanel_(self, sender):
        self.panel_opened += 1

    def convertFont_(self, font):
        return self.chosen if self.chosen is not None else font

    def traitsOfFont_(self, font):
        return font.traits

    def pick(self, family, traits, size=13.0):
        """Fake-only: the user picks a font in the panel, which sends changeFont:."""
        self.chosen = FakeFont(family, traits, size)
        self.target.changeFont_(self)


class NSColor(NSObject):
    @classmethod
    def secondaryLabelColor(cls):
        return "secondaryLabelColor"

    @classmethod
    def blackColor(cls):
        return cls()

    def set(self):
        pass


class NSColorSpace(NSObject):
    def __init__(self, name="sRGB IEC61966-2.1"):
        self._name = name

    @classmethod
    def sRGBColorSpace(cls):
        return cls()

    def localizedName(self):
        return self._name

    def CGColorSpace(self):
        return ("CGColorSpace", self._name)


class Screen:
    """Fake-only NSScreen: just colorSpace()."""

    def __init__(self, name="Adobe RGB (1998)"):
        self._space = NSColorSpace(name)

    def colorSpace(self):
        return self._space


class Layer:
    """Fake-only CAOpenGLLayer: records setColorspace_."""

    def __init__(self):
        self.spaces = []

    def setColorspace_(self, space):
        self.spaces.append(space)


class NSOpenPanel(NSObject):
    result = None  # path the next runModal picks, or None (cancel)

    @classmethod
    def openPanel(cls):
        return cls()

    def setCanChooseFiles_(self, flag):
        pass

    def setCanChooseDirectories_(self, flag):
        pass

    def setAllowsMultipleSelection_(self, flag):
        pass

    def setAllowedFileTypes_(self, types_):
        self.types = list(types_)

    def runModal(self):
        return NSModalResponseOK if NSOpenPanel.result else 0

    def URLs(self):
        return [_URL(NSOpenPanel.result)]


class _URL:
    def __init__(self, path):
        self._path = path

    def path(self):
        return self._path


class NSOpenGLPixelFormat(NSObject):
    def initWithAttributes_(self, _attrs):
        return None  # no GL on Windows: the saver's GL view build fails cleanly


class NSOpenGLView(NSView):
    pass


class _Note:
    def __init__(self, name, obj=None):
        self._name, self._obj = name, obj

    def name(self):
        return self._name

    def object(self):
        return self._obj


class NSDistributedNotificationCenter(NSObject):
    _center = None

    def __init__(self):
        self.posts = []
        self.observers = []

    @classmethod
    def defaultCenter(cls):
        if cls._center is None:
            cls._center = cls()
        return cls._center

    def postNotificationName_object_(self, name, obj):
        self.posts.append((name, obj))

    def addObserver_selector_name_object_(self, observer, selector, name, obj):
        self.observers.append((observer, selector, name, obj))


class _Bundle:
    def __init__(self, ident, path):
        self._ident, self._path = ident, path

    def bundleIdentifier(self):
        return self._ident

    def bundlePath(self):
        return self._path


class NSBundle(NSObject):
    ident = "org.python.python"  # set by the test
    path = "/Library/Frameworks/Python.framework/Versions/3.14/Resources/Python.app"

    @classmethod
    def bundleForClass_(cls, _klass):
        return _Bundle(cls.ident, cls.path)


class ScreenSaverView(NSView):
    def initWithFrame_isPreview_(self, frame, preview):
        self._frame = frame
        return self

    def setAnimationTimeInterval_(self, secs):
        self.interval = secs

    def isAnimating(self):
        return True


class ScreenSaverDefaults(NSObject):
    _by_name = {}

    def __init__(self):
        self.store = {}
        self.sync_result = True
        self.syncs = 0

    @classmethod
    def defaultsForModuleWithName_(cls, name):
        if name not in cls._by_name:
            cls._by_name[name] = cls()
        return cls._by_name[name]

    def synchronize(self):
        self.syncs += 1
        return self.sync_result

    def objectForKey_(self, key):
        return self.store.get(key)

    def setObject_forKey_(self, value, key):
        self.store[key] = value


# Constants
NSButtonTypeSwitch = 3
NSControlStateValueOff = 0
NSControlStateValueOn = 1
NSSegmentSwitchTrackingSelectOne = 0
NSModalResponseOK = 1
NSWindowStyleMaskTitled = 1
NSBackingStoreBuffered = 2
NSViewWidthSizable = 2
NSViewHeightSizable = 16
NSTextAlignmentRight = 2
NSOpenGLPFAAccelerated = 73
NSOpenGLPFAColorSize = 8
NSOpenGLPFADoubleBuffer = 5
NSOpenGLPFAOpenGLProfile = 99
NSOpenGLProfileVersion3_2Core = 0x3200

APPKIT_NAMES = (
    "NSMakeRect",
    "NSRectFill",
    "NSView",
    "NSControl",
    "NSTextField",
    "NSButton",
    "NSSlider",
    "NSPopUpButton",
    "NSSegmentedControl",
    "NSBox",
    "NSScrollView",
    "NSTabView",
    "NSTabViewItem",
    "NSWindow",
    "NSFont",
    "NSColor",
    "NSColorSpace",
    "NSOpenPanel",
    "NSFontManager",
    "NSOpenGLPixelFormat",
    "NSOpenGLView",
    "NSButtonTypeSwitch",
    "NSControlStateValueOff",
    "NSControlStateValueOn",
    "NSSegmentSwitchTrackingSelectOne",
    "NSModalResponseOK",
    "NSWindowStyleMaskTitled",
    "NSBackingStoreBuffered",
    "NSViewWidthSizable",
    "NSViewHeightSizable",
    "NSTextAlignmentRight",
    "NSOpenGLPFAAccelerated",
    "NSOpenGLPFAColorSize",
    "NSOpenGLPFADoubleBuffer",
    "NSOpenGLPFAOpenGLProfile",
    "NSOpenGLProfileVersion3_2Core",
)
FOUNDATION_NAMES = ("NSObject", "NSBundle", "NSDistributedNotificationCenter", "NSMakeRect")


class _ObjCError(Exception):
    """Stands in for objc.error."""


def install():
    """Put the fake modules in sys.modules (replacing any earlier fakes)."""
    g = globals()
    objc = types.ModuleType("objc")
    objc.super = super
    objc.error = _ObjCError
    appkit = types.ModuleType("AppKit")
    for n in APPKIT_NAMES:
        setattr(appkit, n, g[n])
    foundation = types.ModuleType("Foundation")
    for n in FOUNDATION_NAMES:
        setattr(foundation, n, g[n])
    screensaver = types.ModuleType("ScreenSaver")
    screensaver.ScreenSaverView = ScreenSaverView
    screensaver.ScreenSaverDefaults = ScreenSaverDefaults
    sys.modules.update(objc=objc, AppKit=appkit, Foundation=foundation, ScreenSaver=screensaver)


def reset():
    """Empty the fake defaults, notifications and open-panel answer."""
    ScreenSaverDefaults._by_name.clear()
    NSDistributedNotificationCenter._center = None
    NSOpenPanel.result = None
    NSFontManager._shared = None
    NSFontManager.chosen = None
    NSBundle.ident = "org.python.python"
    NSBundle.path = "/Library/Frameworks/Python.framework/Versions/3.14/Resources/Python.app"


def defaults(name="net.phabzlabs.matrixrain"):
    return ScreenSaverDefaults.defaultsForModuleWithName_(name)


def center():
    return NSDistributedNotificationCenter.defaultCenter()
