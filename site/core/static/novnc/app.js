(function() {
    "use strict";

    var $$$core$util$logging$$ = {
            get init_logging() {
                return $$$core$util$logging$$init_logging;
            },

            get get_logging() {
                return $$$core$util$logging$$get_logging;
            },

            get Debug() {
                return $$$core$util$logging$$Debug;
            },

            get Info() {
                return $$$core$util$logging$$Info;
            },

            get Warn() {
                return $$$core$util$logging$$Warn;
            },

            get Error() {
                return $$$core$util$logging$$Error;
            }
        },
        $$$core$util$browser$$ = {
            get isTouchDevice() {
                return $$$core$util$browser$$isTouchDevice;
            },

            get dragThreshold() {
                return $$$core$util$browser$$dragThreshold;
            },

            get supportsCursorURIs() {
                return $$$core$util$browser$$supportsCursorURIs;
            },

            get supportsImageMetadata() {
                return $$$core$util$browser$$supportsImageMetadata;
            },

            get isMac() {
                return $$$core$util$browser$$isMac;
            },

            get isWindows() {
                return $$$core$util$browser$$isWindows;
            },

            get isIOS() {
                return $$$core$util$browser$$isIOS;
            },

            get isAndroid() {
                return $$$core$util$browser$$isAndroid;
            },

            get isSafari() {
                return $$$core$util$browser$$isSafari;
            },

            get isIE() {
                return $$$core$util$browser$$isIE;
            },

            get isEdge() {
                return $$$core$util$browser$$isEdge;
            },

            get isFirefox() {
                return $$$core$util$browser$$isFirefox;
            }
        },
        $$util$$ = {
            get getKeycode() {
                return $$util$$getKeycode;
            },

            get getKey() {
                return $$util$$getKey;
            },

            get getKeysym() {
                return $$util$$getKeysym;
            }
        },
        $$$utils$common$$ = {
            get shrinkBuf() {
                return $$$utils$common$$shrinkBuf;
            },

            get arraySet() {
                return $$$utils$common$$arraySet;
            },

            get flattenChunks() {
                return $$$utils$common$$flattenChunks;
            },

            get Buf8() {
                return $$$utils$common$$Buf8;
            },

            get Buf16() {
                return $$$utils$common$$Buf16;
            },

            get Buf32() {
                return $$$utils$common$$Buf32;
            }
        },
        $$webutil$$ = {
            get init_logging() {
                return $$webutil$$init_logging;
            },

            get getQueryVar() {
                return $$webutil$$getQueryVar;
            },

            get getHashVar() {
                return $$webutil$$getHashVar;
            },

            get getConfigVar() {
                return $$webutil$$getConfigVar;
            },

            get createCookie() {
                return $$webutil$$createCookie;
            },

            get readCookie() {
                return $$webutil$$readCookie;
            },

            get eraseCookie() {
                return $$webutil$$eraseCookie;
            },

            get initSettings() {
                return $$webutil$$initSettings;
            },

            get setSetting() {
                return $$webutil$$setSetting;
            },

            get writeSetting() {
                return $$webutil$$writeSetting;
            },

            get readSetting() {
                return $$webutil$$readSetting;
            },

            get eraseSetting() {
                return $$webutil$$eraseSetting;
            },

            get injectParamIfMissing() {
                return $$webutil$$injectParamIfMissing;
            },

            get fetchJSON() {
                return $$webutil$$fetchJSON;
            }
        };

    /*
     * noVNC: HTML5 VNC client
     * Copyright (C) 2018 The noVNC Authors
     * Licensed under MPL 2.0 (see LICENSE.txt)
     *
     * See README.md for usage and integration instructions.
     */

    /*
     * Logging/debug routines
     */

    let $$$core$util$logging$$_log_level = 'warn';

    let $$$core$util$logging$$Debug = () => {};
    let $$$core$util$logging$$Info = () => {};
    let $$$core$util$logging$$Warn = () => {};
    let $$$core$util$logging$$Error = () => {};

    function $$$core$util$logging$$init_logging(level) {
        if (typeof level === 'undefined') {
            level = $$$core$util$logging$$_log_level;
        } else {
            $$$core$util$logging$$_log_level = level;
        }

        $$$core$util$logging$$Debug = $$$core$util$logging$$Info = $$$core$util$logging$$Warn = $$$core$util$logging$$Error = () => {};

        if (typeof window.console !== "undefined") {
            /* eslint-disable no-console, no-fallthrough */
            switch (level) {
                case 'debug':
                    $$$core$util$logging$$Debug = console.debug.bind(window.console);
                case 'info':
                    $$$core$util$logging$$Info  = console.info.bind(window.console);
                case 'warn':
                    $$$core$util$logging$$Warn  = console.warn.bind(window.console);
                case 'error':
                    $$$core$util$logging$$Error = console.error.bind(window.console);
                case 'none':
                    break;
                default:
                    throw new window.Error("invalid logging type '" + level + "'");
            }
            /* eslint-enable no-console, no-fallthrough */
        }
    }

    function $$$core$util$logging$$get_logging() {
        return $$$core$util$logging$$_log_level;
    }

    // Initialize logging level
    $$$core$util$logging$$init_logging();

    class $$localization$$Localizer {
        constructor() {
            // Currently configured language
            this.language = 'en';

            // Current dictionary of translations
            this.dictionary = undefined;
        }

        // Configure suitable language based on user preferences
        setup(supportedLanguages) {
            this.language = 'en'; // Default: US English

            /*
             * Navigator.languages only available in Chrome (32+) and FireFox (32+)
             * Fall back to navigator.language for other browsers
             */
            let userLanguages;
            if (typeof window.navigator.languages == 'object') {
                userLanguages = window.navigator.languages;
            } else {
                userLanguages = [navigator.language || navigator.userLanguage];
            }

            for (let i = 0;i < userLanguages.length;i++) {
                const userLang = userLanguages[i]
                    .toLowerCase()
                    .replace("_", "-")
                    .split("-");

                // Built-in default?
                if ((userLang[0] === 'en') &&
                    ((userLang[1] === undefined) || (userLang[1] === 'us'))) {
                    return;
                }

                // First pass: perfect match
                for (let j = 0; j < supportedLanguages.length; j++) {
                    const supLang = supportedLanguages[j]
                        .toLowerCase()
                        .replace("_", "-")
                        .split("-");

                    if (userLang[0] !== supLang[0]) {
                        continue;
                    }
                    if (userLang[1] !== supLang[1]) {
                        continue;
                    }

                    this.language = supportedLanguages[j];
                    return;
                }

                // Second pass: fallback
                for (let j = 0;j < supportedLanguages.length;j++) {
                    const supLang = supportedLanguages[j]
                        .toLowerCase()
                        .replace("_", "-")
                        .split("-");

                    if (userLang[0] !== supLang[0]) {
                        continue;
                    }
                    if (supLang[1] !== undefined) {
                        continue;
                    }

                    this.language = supportedLanguages[j];
                    return;
                }
            }
        }

        // Retrieve localised text
        get(id) {
            if (typeof this.dictionary !== 'undefined' && this.dictionary[id]) {
                return this.dictionary[id];
            } else {
                return id;
            }
        }

        // Traverses the DOM and translates relevant fields
        // See https://html.spec.whatwg.org/multipage/dom.html#attr-translate
        translateDOM() {
            const self = this;

            function process(elem, enabled) {
                function isAnyOf(searchElement, items) {
                    return items.indexOf(searchElement) !== -1;
                }

                function translateAttribute(elem, attr) {
                    const str = self.get(elem.getAttribute(attr));
                    elem.setAttribute(attr, str);
                }

                function translateTextNode(node) {
                    const str = self.get(node.data.trim());
                    node.data = str;
                }

                if (elem.hasAttribute("translate")) {
                    if (isAnyOf(elem.getAttribute("translate"), ["", "yes"])) {
                        enabled = true;
                    } else if (isAnyOf(elem.getAttribute("translate"), ["no"])) {
                        enabled = false;
                    }
                }

                if (enabled) {
                    if (elem.hasAttribute("abbr") &&
                        elem.tagName === "TH") {
                        translateAttribute(elem, "abbr");
                    }
                    if (elem.hasAttribute("alt") &&
                        isAnyOf(elem.tagName, ["AREA", "IMG", "INPUT"])) {
                        translateAttribute(elem, "alt");
                    }
                    if (elem.hasAttribute("download") &&
                        isAnyOf(elem.tagName, ["A", "AREA"])) {
                        translateAttribute(elem, "download");
                    }
                    if (elem.hasAttribute("label") &&
                        isAnyOf(elem.tagName, ["MENUITEM", "MENU", "OPTGROUP",
                                               "OPTION", "TRACK"])) {
                        translateAttribute(elem, "label");
                    }
                    // FIXME: Should update "lang"
                    if (elem.hasAttribute("placeholder") &&
                        isAnyOf(elem.tagName, ["INPUT", "TEXTAREA"])) {
                        translateAttribute(elem, "placeholder");
                    }
                    if (elem.hasAttribute("title")) {
                        translateAttribute(elem, "title");
                    }
                    if (elem.hasAttribute("value") &&
                        elem.tagName === "INPUT" &&
                        isAnyOf(elem.getAttribute("type"), ["reset", "button", "submit"])) {
                        translateAttribute(elem, "value");
                    }
                }

                for (let i = 0; i < elem.childNodes.length; i++) {
                    const node = elem.childNodes[i];
                    if (node.nodeType === node.ELEMENT_NODE) {
                        process(node, enabled);
                    } else if (node.nodeType === node.TEXT_NODE && enabled) {
                        translateTextNode(node);
                    }
                }
            }

            process(document.body, true);
        }
    }

    const $$localization$$l10n = new $$localization$$Localizer();
    var $$localization$$default = $$localization$$l10n.get.bind($$localization$$l10n);

    let $$$core$util$browser$$isTouchDevice = ('ontouchstart' in document.documentElement) ||
                                     // requried for Chrome debugger
                                     (document.ontouchstart !== undefined) ||
                                     // required for MS Surface
                                     (navigator.maxTouchPoints > 0) ||
                                     (navigator.msMaxTouchPoints > 0);

    window.addEventListener('touchstart', function onFirstTouch() {
        $$$core$util$browser$$isTouchDevice = true;
        window.removeEventListener('touchstart', onFirstTouch, false);
    }, false);


    let $$$core$util$browser$$dragThreshold = 10 * (window.devicePixelRatio || 1);

    let $$$core$util$browser$$_supportsCursorURIs = false;

    try {
        const $$$core$util$browser$$target = document.createElement('canvas');
        $$$core$util$browser$$target.style.cursor = 'url("data:image/x-icon;base64,AAACAAEACAgAAAIAAgA4AQAAFgAAACgAAAAIAAAAEAAAAAEAIAAAAAAAEAAAAAAAAAAAAAAAAAAAAAAAAAD/////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////AAAAAAAAAAAAAAAAAAAAAA==") 2 2, default';

        if ($$$core$util$browser$$target.style.cursor) {
            $$$core$util$logging$$.Info("Data URI scheme cursor supported");
            $$$core$util$browser$$_supportsCursorURIs = true;
        } else {
            $$$core$util$logging$$.Warn("Data URI scheme cursor not supported");
        }
    } catch (exc) {
        $$$core$util$logging$$.Error("Data URI scheme cursor test exception: " + exc);
    }

    const $$$core$util$browser$$supportsCursorURIs = $$$core$util$browser$$_supportsCursorURIs;

    let $$$core$util$browser$$_supportsImageMetadata = false;
    try {
        new ImageData(new Uint8ClampedArray(4), 1, 1);
        $$$core$util$browser$$_supportsImageMetadata = true;
    } catch (ex) {
        // ignore failure
    }
    const $$$core$util$browser$$supportsImageMetadata = $$$core$util$browser$$_supportsImageMetadata;

    function $$$core$util$browser$$isMac() {
        return navigator && !!(/mac/i).exec(navigator.platform);
    }

    function $$$core$util$browser$$isWindows() {
        return navigator && !!(/win/i).exec(navigator.platform);
    }

    function $$$core$util$browser$$isIOS() {
        return navigator &&
               (!!(/ipad/i).exec(navigator.platform) ||
                !!(/iphone/i).exec(navigator.platform) ||
                !!(/ipod/i).exec(navigator.platform));
    }

    function $$$core$util$browser$$isAndroid() {
        return navigator && !!(/android/i).exec(navigator.userAgent);
    }

    function $$$core$util$browser$$isSafari() {
        return navigator && (navigator.userAgent.indexOf('Safari') !== -1 &&
                             navigator.userAgent.indexOf('Chrome') === -1);
    }

    function $$$core$util$browser$$isIE() {
        return navigator && !!(/trident/i).exec(navigator.userAgent);
    }

    function $$$core$util$browser$$isEdge() {
        return navigator && !!(/edge/i).exec(navigator.userAgent);
    }

    function $$$core$util$browser$$isFirefox() {
        return navigator && !!(/firefox/i).exec(navigator.userAgent);
    }

    function $$$core$util$events$$getPointerEvent(e) {
        return e.changedTouches ? e.changedTouches[0] : e.touches ? e.touches[0] : e;
    }

    function $$$core$util$events$$stopEvent(e) {
        e.stopPropagation();
        e.preventDefault();
    }

    // Emulate Element.setCapture() when not supported
    let $$$core$util$events$$_captureRecursion = false;
    let $$$core$util$events$$_captureElem = null;
    function $$$core$util$events$$_captureProxy(e) {
        // Recursion protection as we'll see our own event
        if ($$$core$util$events$$_captureRecursion) return;

        // Clone the event as we cannot dispatch an already dispatched event
        const newEv = new e.constructor(e.type, e);

        $$$core$util$events$$_captureRecursion = true;
        $$$core$util$events$$_captureElem.dispatchEvent(newEv);
        $$$core$util$events$$_captureRecursion = false;

        // Avoid double events
        e.stopPropagation();

        // Respect the wishes of the redirected event handlers
        if (newEv.defaultPrevented) {
            e.preventDefault();
        }

        // Implicitly release the capture on button release
        if (e.type === "mouseup") {
            $$$core$util$events$$releaseCapture();
        }
    }

    // Follow cursor style of target element
    function $$$core$util$events$$_captureElemChanged() {
        const captureElem = document.getElementById("noVNC_mouse_capture_elem");
        captureElem.style.cursor = window.getComputedStyle($$$core$util$events$$_captureElem).cursor;
    }

    const $$$core$util$events$$_captureObserver = new MutationObserver($$$core$util$events$$_captureElemChanged);

    let $$$core$util$events$$_captureIndex = 0;

    function $$$core$util$events$$setCapture(elem) {
        if (elem.setCapture) {

            elem.setCapture();

            // IE releases capture on 'click' events which might not trigger
            elem.addEventListener('mouseup', $$$core$util$events$$releaseCapture);

        } else {
            // Release any existing capture in case this method is
            // called multiple times without coordination
            $$$core$util$events$$releaseCapture();

            let captureElem = document.getElementById("noVNC_mouse_capture_elem");

            if (captureElem === null) {
                captureElem = document.createElement("div");
                captureElem.id = "noVNC_mouse_capture_elem";
                captureElem.style.position = "fixed";
                captureElem.style.top = "0px";
                captureElem.style.left = "0px";
                captureElem.style.width = "100%";
                captureElem.style.height = "100%";
                captureElem.style.zIndex = 10000;
                captureElem.style.display = "none";
                document.body.appendChild(captureElem);

                // This is to make sure callers don't get confused by having
                // our blocking element as the target
                captureElem.addEventListener('contextmenu', $$$core$util$events$$_captureProxy);

                captureElem.addEventListener('mousemove', $$$core$util$events$$_captureProxy);
                captureElem.addEventListener('mouseup', $$$core$util$events$$_captureProxy);
            }

            $$$core$util$events$$_captureElem = elem;
            $$$core$util$events$$_captureIndex++;

            // Track cursor and get initial cursor
            $$$core$util$events$$_captureObserver.observe(elem, {attributes: true});
            $$$core$util$events$$_captureElemChanged();

            captureElem.style.display = "";

            // We listen to events on window in order to keep tracking if it
            // happens to leave the viewport
            window.addEventListener('mousemove', $$$core$util$events$$_captureProxy);
            window.addEventListener('mouseup', $$$core$util$events$$_captureProxy);
        }
    }

    function $$$core$util$events$$releaseCapture() {
        if (document.releaseCapture) {

            document.releaseCapture();

        } else {
            if (!$$$core$util$events$$_captureElem) {
                return;
            }

            // There might be events already queued, so we need to wait for
            // them to flush. E.g. contextmenu in Microsoft Edge
            window.setTimeout((expected) => {
                // Only clear it if it's the expected grab (i.e. no one
                // else has initiated a new grab)
                if ($$$core$util$events$$_captureIndex === expected) {
                    $$$core$util$events$$_captureElem = null;
                }
            }, 0, $$$core$util$events$$_captureIndex);

            $$$core$util$events$$_captureObserver.disconnect();

            const captureElem = document.getElementById("noVNC_mouse_capture_elem");
            captureElem.style.display = "none";

            window.removeEventListener('mousemove', $$$core$util$events$$_captureProxy);
            window.removeEventListener('mouseup', $$$core$util$events$$_captureProxy);
        }
    }

    var $$$core$input$keysym$$default = {
        XK_VoidSymbol:                  0xffffff,

        /* Void symbol */

        XK_BackSpace:                   0xff08,

        /* Back space, back char */
        XK_Tab:                         0xff09,

        XK_Linefeed:                    0xff0a,

        /* Linefeed, LF */
        XK_Clear:                       0xff0b,

        XK_Return:                      0xff0d,

        /* Return, enter */
        XK_Pause:                       0xff13,

        /* Pause, hold */
        XK_Scroll_Lock:                 0xff14,

        XK_Sys_Req:                     0xff15,
        XK_Escape:                      0xff1b,
        XK_Delete:                      0xffff,

        /* Delete, rubout */

        /* International & multi-key character composition */

        XK_Multi_key:                   0xff20,

        /* Multi-key character compose */
        XK_Codeinput:                   0xff37,

        XK_SingleCandidate:             0xff3c,
        XK_MultipleCandidate:           0xff3d,
        XK_PreviousCandidate:           0xff3e,

        /* Japanese keyboard support */

        XK_Kanji:                       0xff21,

        /* Kanji, Kanji convert */
        XK_Muhenkan:                    0xff22,

        /* Cancel Conversion */
        XK_Henkan_Mode:                 0xff23,

        /* Start/Stop Conversion */
        XK_Henkan:                      0xff23,

        /* Alias for Henkan_Mode */
        XK_Romaji:                      0xff24,

        /* to Romaji */
        XK_Hiragana:                    0xff25,

        /* to Hiragana */
        XK_Katakana:                    0xff26,

        /* to Katakana */
        XK_Hiragana_Katakana:           0xff27,

        /* Hiragana/Katakana toggle */
        XK_Zenkaku:                     0xff28,

        /* to Zenkaku */
        XK_Hankaku:                     0xff29,

        /* to Hankaku */
        XK_Zenkaku_Hankaku:             0xff2a,

        /* Zenkaku/Hankaku toggle */
        XK_Touroku:                     0xff2b,

        /* Add to Dictionary */
        XK_Massyo:                      0xff2c,

        /* Delete from Dictionary */
        XK_Kana_Lock:                   0xff2d,

        /* Kana Lock */
        XK_Kana_Shift:                  0xff2e,

        /* Kana Shift */
        XK_Eisu_Shift:                  0xff2f,

        /* Alphanumeric Shift */
        XK_Eisu_toggle:                 0xff30,

        /* Alphanumeric toggle */
        XK_Kanji_Bangou:                0xff37,

        /* Codeinput */
        XK_Zen_Koho:                    0xff3d,

        /* Multiple/All Candidate(s) */
        XK_Mae_Koho:                    0xff3e,

        /* Previous Candidate */

        /* Cursor control & motion */

        XK_Home:                        0xff50,

        XK_Left:                        0xff51,

        /* Move left, left arrow */
        XK_Up:                          0xff52,

        /* Move up, up arrow */
        XK_Right:                       0xff53,

        /* Move right, right arrow */
        XK_Down:                        0xff54,

        /* Move down, down arrow */
        XK_Prior:                       0xff55,

        /* Prior, previous */
        XK_Page_Up:                     0xff55,

        XK_Next:                        0xff56,

        /* Next */
        XK_Page_Down:                   0xff56,

        XK_End:                         0xff57,

        /* EOL */
        XK_Begin:                       0xff58,

        /* BOL */


        /* Misc functions */

        XK_Select:                      0xff60,

        /* Select, mark */
        XK_Print:                       0xff61,

        XK_Execute:                     0xff62,

        /* Execute, run, do */
        XK_Insert:                      0xff63,

        /* Insert, insert here */
        XK_Undo:                        0xff65,

        XK_Redo:                        0xff66,

        /* Redo, again */
        XK_Menu:                        0xff67,

        XK_Find:                        0xff68,

        /* Find, search */
        XK_Cancel:                      0xff69,

        /* Cancel, stop, abort, exit */
        XK_Help:                        0xff6a,

        /* Help */
        XK_Break:                       0xff6b,

        XK_Mode_switch:                 0xff7e,

        /* Character set switch */
        XK_script_switch:               0xff7e,

        /* Alias for mode_switch */
        XK_Num_Lock:                    0xff7f,

        /* Keypad functions, keypad numbers cleverly chosen to map to ASCII */

        XK_KP_Space:                    0xff80,

        /* Space */
        XK_KP_Tab:                      0xff89,

        XK_KP_Enter:                    0xff8d,

        /* Enter */
        XK_KP_F1:                       0xff91,

        /* PF1, KP_A, ... */
        XK_KP_F2:                       0xff92,

        XK_KP_F3:                       0xff93,
        XK_KP_F4:                       0xff94,
        XK_KP_Home:                     0xff95,
        XK_KP_Left:                     0xff96,
        XK_KP_Up:                       0xff97,
        XK_KP_Right:                    0xff98,
        XK_KP_Down:                     0xff99,
        XK_KP_Prior:                    0xff9a,
        XK_KP_Page_Up:                  0xff9a,
        XK_KP_Next:                     0xff9b,
        XK_KP_Page_Down:                0xff9b,
        XK_KP_End:                      0xff9c,
        XK_KP_Begin:                    0xff9d,
        XK_KP_Insert:                   0xff9e,
        XK_KP_Delete:                   0xff9f,
        XK_KP_Equal:                    0xffbd,

        /* Equals */
        XK_KP_Multiply:                 0xffaa,

        XK_KP_Add:                      0xffab,
        XK_KP_Separator:                0xffac,

        /* Separator, often comma */
        XK_KP_Subtract:                 0xffad,

        XK_KP_Decimal:                  0xffae,
        XK_KP_Divide:                   0xffaf,
        XK_KP_0:                        0xffb0,
        XK_KP_1:                        0xffb1,
        XK_KP_2:                        0xffb2,
        XK_KP_3:                        0xffb3,
        XK_KP_4:                        0xffb4,
        XK_KP_5:                        0xffb5,
        XK_KP_6:                        0xffb6,
        XK_KP_7:                        0xffb7,
        XK_KP_8:                        0xffb8,
        XK_KP_9:                        0xffb9,

        /*
         * Auxiliary functions; note the duplicate definitions for left and right
         * function keys;  Sun keyboards and a few other manufacturers have such
         * function key groups on the left and/or right sides of the keyboard.
         * We've not found a keyboard with more than 35 function keys total.
         */

        XK_F1:                          0xffbe,

        XK_F2:                          0xffbf,
        XK_F3:                          0xffc0,
        XK_F4:                          0xffc1,
        XK_F5:                          0xffc2,
        XK_F6:                          0xffc3,
        XK_F7:                          0xffc4,
        XK_F8:                          0xffc5,
        XK_F9:                          0xffc6,
        XK_F10:                         0xffc7,
        XK_F11:                         0xffc8,
        XK_L1:                          0xffc8,
        XK_F12:                         0xffc9,
        XK_L2:                          0xffc9,
        XK_F13:                         0xffca,
        XK_L3:                          0xffca,
        XK_F14:                         0xffcb,
        XK_L4:                          0xffcb,
        XK_F15:                         0xffcc,
        XK_L5:                          0xffcc,
        XK_F16:                         0xffcd,
        XK_L6:                          0xffcd,
        XK_F17:                         0xffce,
        XK_L7:                          0xffce,
        XK_F18:                         0xffcf,
        XK_L8:                          0xffcf,
        XK_F19:                         0xffd0,
        XK_L9:                          0xffd0,
        XK_F20:                         0xffd1,
        XK_L10:                         0xffd1,
        XK_F21:                         0xffd2,
        XK_R1:                          0xffd2,
        XK_F22:                         0xffd3,
        XK_R2:                          0xffd3,
        XK_F23:                         0xffd4,
        XK_R3:                          0xffd4,
        XK_F24:                         0xffd5,
        XK_R4:                          0xffd5,
        XK_F25:                         0xffd6,
        XK_R5:                          0xffd6,
        XK_F26:                         0xffd7,
        XK_R6:                          0xffd7,
        XK_F27:                         0xffd8,
        XK_R7:                          0xffd8,
        XK_F28:                         0xffd9,
        XK_R8:                          0xffd9,
        XK_F29:                         0xffda,
        XK_R9:                          0xffda,
        XK_F30:                         0xffdb,
        XK_R10:                         0xffdb,
        XK_F31:                         0xffdc,
        XK_R11:                         0xffdc,
        XK_F32:                         0xffdd,
        XK_R12:                         0xffdd,
        XK_F33:                         0xffde,
        XK_R13:                         0xffde,
        XK_F34:                         0xffdf,
        XK_R14:                         0xffdf,
        XK_F35:                         0xffe0,
        XK_R15:                         0xffe0,

        /* Modifiers */

        XK_Shift_L:                     0xffe1,

        /* Left shift */
        XK_Shift_R:                     0xffe2,

        /* Right shift */
        XK_Control_L:                   0xffe3,

        /* Left control */
        XK_Control_R:                   0xffe4,

        /* Right control */
        XK_Caps_Lock:                   0xffe5,

        /* Caps lock */
        XK_Shift_Lock:                  0xffe6,

        /* Shift lock */

        XK_Meta_L:                      0xffe7,

        /* Left meta */
        XK_Meta_R:                      0xffe8,

        /* Right meta */
        XK_Alt_L:                       0xffe9,

        /* Left alt */
        XK_Alt_R:                       0xffea,

        /* Right alt */
        XK_Super_L:                     0xffeb,

        /* Left super */
        XK_Super_R:                     0xffec,

        /* Right super */
        XK_Hyper_L:                     0xffed,

        /* Left hyper */
        XK_Hyper_R:                     0xffee,

        /* Right hyper */

        /*
         * Keyboard (XKB) Extension function and modifier keys
         * (from Appendix C of "The X Keyboard Extension: Protocol Specification")
         * Byte 3 = 0xfe
         */

        XK_ISO_Level3_Shift:            0xfe03,

        /* AltGr */
        XK_ISO_Next_Group:              0xfe08,

        XK_ISO_Prev_Group:              0xfe0a,
        XK_ISO_First_Group:             0xfe0c,
        XK_ISO_Last_Group:              0xfe0e,

        /*
         * Latin 1
         * (ISO/IEC 8859-1: Unicode U+0020..U+00FF)
         * Byte 3: 0
         */

        XK_space:                       0x0020,

        /* U+0020 SPACE */
        XK_exclam:                      0x0021,

        /* U+0021 EXCLAMATION MARK */
        XK_quotedbl:                    0x0022,

        /* U+0022 QUOTATION MARK */
        XK_numbersign:                  0x0023,

        /* U+0023 NUMBER SIGN */
        XK_dollar:                      0x0024,

        /* U+0024 DOLLAR SIGN */
        XK_percent:                     0x0025,

        /* U+0025 PERCENT SIGN */
        XK_ampersand:                   0x0026,

        /* U+0026 AMPERSAND */
        XK_apostrophe:                  0x0027,

        /* U+0027 APOSTROPHE */
        XK_quoteright:                  0x0027,

        /* deprecated */
        XK_parenleft:                   0x0028,

        /* U+0028 LEFT PARENTHESIS */
        XK_parenright:                  0x0029,

        /* U+0029 RIGHT PARENTHESIS */
        XK_asterisk:                    0x002a,

        /* U+002A ASTERISK */
        XK_plus:                        0x002b,

        /* U+002B PLUS SIGN */
        XK_comma:                       0x002c,

        /* U+002C COMMA */
        XK_minus:                       0x002d,

        /* U+002D HYPHEN-MINUS */
        XK_period:                      0x002e,

        /* U+002E FULL STOP */
        XK_slash:                       0x002f,

        /* U+002F SOLIDUS */
        XK_0:                           0x0030,

        /* U+0030 DIGIT ZERO */
        XK_1:                           0x0031,

        /* U+0031 DIGIT ONE */
        XK_2:                           0x0032,

        /* U+0032 DIGIT TWO */
        XK_3:                           0x0033,

        /* U+0033 DIGIT THREE */
        XK_4:                           0x0034,

        /* U+0034 DIGIT FOUR */
        XK_5:                           0x0035,

        /* U+0035 DIGIT FIVE */
        XK_6:                           0x0036,

        /* U+0036 DIGIT SIX */
        XK_7:                           0x0037,

        /* U+0037 DIGIT SEVEN */
        XK_8:                           0x0038,

        /* U+0038 DIGIT EIGHT */
        XK_9:                           0x0039,

        /* U+0039 DIGIT NINE */
        XK_colon:                       0x003a,

        /* U+003A COLON */
        XK_semicolon:                   0x003b,

        /* U+003B SEMICOLON */
        XK_less:                        0x003c,

        /* U+003C LESS-THAN SIGN */
        XK_equal:                       0x003d,

        /* U+003D EQUALS SIGN */
        XK_greater:                     0x003e,

        /* U+003E GREATER-THAN SIGN */
        XK_question:                    0x003f,

        /* U+003F QUESTION MARK */
        XK_at:                          0x0040,

        /* U+0040 COMMERCIAL AT */
        XK_A:                           0x0041,

        /* U+0041 LATIN CAPITAL LETTER A */
        XK_B:                           0x0042,

        /* U+0042 LATIN CAPITAL LETTER B */
        XK_C:                           0x0043,

        /* U+0043 LATIN CAPITAL LETTER C */
        XK_D:                           0x0044,

        /* U+0044 LATIN CAPITAL LETTER D */
        XK_E:                           0x0045,

        /* U+0045 LATIN CAPITAL LETTER E */
        XK_F:                           0x0046,

        /* U+0046 LATIN CAPITAL LETTER F */
        XK_G:                           0x0047,

        /* U+0047 LATIN CAPITAL LETTER G */
        XK_H:                           0x0048,

        /* U+0048 LATIN CAPITAL LETTER H */
        XK_I:                           0x0049,

        /* U+0049 LATIN CAPITAL LETTER I */
        XK_J:                           0x004a,

        /* U+004A LATIN CAPITAL LETTER J */
        XK_K:                           0x004b,

        /* U+004B LATIN CAPITAL LETTER K */
        XK_L:                           0x004c,

        /* U+004C LATIN CAPITAL LETTER L */
        XK_M:                           0x004d,

        /* U+004D LATIN CAPITAL LETTER M */
        XK_N:                           0x004e,

        /* U+004E LATIN CAPITAL LETTER N */
        XK_O:                           0x004f,

        /* U+004F LATIN CAPITAL LETTER O */
        XK_P:                           0x0050,

        /* U+0050 LATIN CAPITAL LETTER P */
        XK_Q:                           0x0051,

        /* U+0051 LATIN CAPITAL LETTER Q */
        XK_R:                           0x0052,

        /* U+0052 LATIN CAPITAL LETTER R */
        XK_S:                           0x0053,

        /* U+0053 LATIN CAPITAL LETTER S */
        XK_T:                           0x0054,

        /* U+0054 LATIN CAPITAL LETTER T */
        XK_U:                           0x0055,

        /* U+0055 LATIN CAPITAL LETTER U */
        XK_V:                           0x0056,

        /* U+0056 LATIN CAPITAL LETTER V */
        XK_W:                           0x0057,

        /* U+0057 LATIN CAPITAL LETTER W */
        XK_X:                           0x0058,

        /* U+0058 LATIN CAPITAL LETTER X */
        XK_Y:                           0x0059,

        /* U+0059 LATIN CAPITAL LETTER Y */
        XK_Z:                           0x005a,

        /* U+005A LATIN CAPITAL LETTER Z */
        XK_bracketleft:                 0x005b,

        /* U+005B LEFT SQUARE BRACKET */
        XK_backslash:                   0x005c,

        /* U+005C REVERSE SOLIDUS */
        XK_bracketright:                0x005d,

        /* U+005D RIGHT SQUARE BRACKET */
        XK_asciicircum:                 0x005e,

        /* U+005E CIRCUMFLEX ACCENT */
        XK_underscore:                  0x005f,

        /* U+005F LOW LINE */
        XK_grave:                       0x0060,

        /* U+0060 GRAVE ACCENT */
        XK_quoteleft:                   0x0060,

        /* deprecated */
        XK_a:                           0x0061,

        /* U+0061 LATIN SMALL LETTER A */
        XK_b:                           0x0062,

        /* U+0062 LATIN SMALL LETTER B */
        XK_c:                           0x0063,

        /* U+0063 LATIN SMALL LETTER C */
        XK_d:                           0x0064,

        /* U+0064 LATIN SMALL LETTER D */
        XK_e:                           0x0065,

        /* U+0065 LATIN SMALL LETTER E */
        XK_f:                           0x0066,

        /* U+0066 LATIN SMALL LETTER F */
        XK_g:                           0x0067,

        /* U+0067 LATIN SMALL LETTER G */
        XK_h:                           0x0068,

        /* U+0068 LATIN SMALL LETTER H */
        XK_i:                           0x0069,

        /* U+0069 LATIN SMALL LETTER I */
        XK_j:                           0x006a,

        /* U+006A LATIN SMALL LETTER J */
        XK_k:                           0x006b,

        /* U+006B LATIN SMALL LETTER K */
        XK_l:                           0x006c,

        /* U+006C LATIN SMALL LETTER L */
        XK_m:                           0x006d,

        /* U+006D LATIN SMALL LETTER M */
        XK_n:                           0x006e,

        /* U+006E LATIN SMALL LETTER N */
        XK_o:                           0x006f,

        /* U+006F LATIN SMALL LETTER O */
        XK_p:                           0x0070,

        /* U+0070 LATIN SMALL LETTER P */
        XK_q:                           0x0071,

        /* U+0071 LATIN SMALL LETTER Q */
        XK_r:                           0x0072,

        /* U+0072 LATIN SMALL LETTER R */
        XK_s:                           0x0073,

        /* U+0073 LATIN SMALL LETTER S */
        XK_t:                           0x0074,

        /* U+0074 LATIN SMALL LETTER T */
        XK_u:                           0x0075,

        /* U+0075 LATIN SMALL LETTER U */
        XK_v:                           0x0076,

        /* U+0076 LATIN SMALL LETTER V */
        XK_w:                           0x0077,

        /* U+0077 LATIN SMALL LETTER W */
        XK_x:                           0x0078,

        /* U+0078 LATIN SMALL LETTER X */
        XK_y:                           0x0079,

        /* U+0079 LATIN SMALL LETTER Y */
        XK_z:                           0x007a,

        /* U+007A LATIN SMALL LETTER Z */
        XK_braceleft:                   0x007b,

        /* U+007B LEFT CURLY BRACKET */
        XK_bar:                         0x007c,

        /* U+007C VERTICAL LINE */
        XK_braceright:                  0x007d,

        /* U+007D RIGHT CURLY BRACKET */
        XK_asciitilde:                  0x007e,

        /* U+007E TILDE */

        XK_nobreakspace:                0x00a0,

        /* U+00A0 NO-BREAK SPACE */
        XK_exclamdown:                  0x00a1,

        /* U+00A1 INVERTED EXCLAMATION MARK */
        XK_cent:                        0x00a2,

        /* U+00A2 CENT SIGN */
        XK_sterling:                    0x00a3,

        /* U+00A3 POUND SIGN */
        XK_currency:                    0x00a4,

        /* U+00A4 CURRENCY SIGN */
        XK_yen:                         0x00a5,

        /* U+00A5 YEN SIGN */
        XK_brokenbar:                   0x00a6,

        /* U+00A6 BROKEN BAR */
        XK_section:                     0x00a7,

        /* U+00A7 SECTION SIGN */
        XK_diaeresis:                   0x00a8,

        /* U+00A8 DIAERESIS */
        XK_copyright:                   0x00a9,

        /* U+00A9 COPYRIGHT SIGN */
        XK_ordfeminine:                 0x00aa,

        /* U+00AA FEMININE ORDINAL INDICATOR */
        XK_guillemotleft:               0x00ab,

        /* U+00AB LEFT-POINTING DOUBLE ANGLE QUOTATION MARK */
        XK_notsign:                     0x00ac,

        /* U+00AC NOT SIGN */
        XK_hyphen:                      0x00ad,

        /* U+00AD SOFT HYPHEN */
        XK_registered:                  0x00ae,

        /* U+00AE REGISTERED SIGN */
        XK_macron:                      0x00af,

        /* U+00AF MACRON */
        XK_degree:                      0x00b0,

        /* U+00B0 DEGREE SIGN */
        XK_plusminus:                   0x00b1,

        /* U+00B1 PLUS-MINUS SIGN */
        XK_twosuperior:                 0x00b2,

        /* U+00B2 SUPERSCRIPT TWO */
        XK_threesuperior:               0x00b3,

        /* U+00B3 SUPERSCRIPT THREE */
        XK_acute:                       0x00b4,

        /* U+00B4 ACUTE ACCENT */
        XK_mu:                          0x00b5,

        /* U+00B5 MICRO SIGN */
        XK_paragraph:                   0x00b6,

        /* U+00B6 PILCROW SIGN */
        XK_periodcentered:              0x00b7,

        /* U+00B7 MIDDLE DOT */
        XK_cedilla:                     0x00b8,

        /* U+00B8 CEDILLA */
        XK_onesuperior:                 0x00b9,

        /* U+00B9 SUPERSCRIPT ONE */
        XK_masculine:                   0x00ba,

        /* U+00BA MASCULINE ORDINAL INDICATOR */
        XK_guillemotright:              0x00bb,

        /* U+00BB RIGHT-POINTING DOUBLE ANGLE QUOTATION MARK */
        XK_onequarter:                  0x00bc,

        /* U+00BC VULGAR FRACTION ONE QUARTER */
        XK_onehalf:                     0x00bd,

        /* U+00BD VULGAR FRACTION ONE HALF */
        XK_threequarters:               0x00be,

        /* U+00BE VULGAR FRACTION THREE QUARTERS */
        XK_questiondown:                0x00bf,

        /* U+00BF INVERTED QUESTION MARK */
        XK_Agrave:                      0x00c0,

        /* U+00C0 LATIN CAPITAL LETTER A WITH GRAVE */
        XK_Aacute:                      0x00c1,

        /* U+00C1 LATIN CAPITAL LETTER A WITH ACUTE */
        XK_Acircumflex:                 0x00c2,

        /* U+00C2 LATIN CAPITAL LETTER A WITH CIRCUMFLEX */
        XK_Atilde:                      0x00c3,

        /* U+00C3 LATIN CAPITAL LETTER A WITH TILDE */
        XK_Adiaeresis:                  0x00c4,

        /* U+00C4 LATIN CAPITAL LETTER A WITH DIAERESIS */
        XK_Aring:                       0x00c5,

        /* U+00C5 LATIN CAPITAL LETTER A WITH RING ABOVE */
        XK_AE:                          0x00c6,

        /* U+00C6 LATIN CAPITAL LETTER AE */
        XK_Ccedilla:                    0x00c7,

        /* U+00C7 LATIN CAPITAL LETTER C WITH CEDILLA */
        XK_Egrave:                      0x00c8,

        /* U+00C8 LATIN CAPITAL LETTER E WITH GRAVE */
        XK_Eacute:                      0x00c9,

        /* U+00C9 LATIN CAPITAL LETTER E WITH ACUTE */
        XK_Ecircumflex:                 0x00ca,

        /* U+00CA LATIN CAPITAL LETTER E WITH CIRCUMFLEX */
        XK_Ediaeresis:                  0x00cb,

        /* U+00CB LATIN CAPITAL LETTER E WITH DIAERESIS */
        XK_Igrave:                      0x00cc,

        /* U+00CC LATIN CAPITAL LETTER I WITH GRAVE */
        XK_Iacute:                      0x00cd,

        /* U+00CD LATIN CAPITAL LETTER I WITH ACUTE */
        XK_Icircumflex:                 0x00ce,

        /* U+00CE LATIN CAPITAL LETTER I WITH CIRCUMFLEX */
        XK_Idiaeresis:                  0x00cf,

        /* U+00CF LATIN CAPITAL LETTER I WITH DIAERESIS */
        XK_ETH:                         0x00d0,

        /* U+00D0 LATIN CAPITAL LETTER ETH */
        XK_Eth:                         0x00d0,

        /* deprecated */
        XK_Ntilde:                      0x00d1,

        /* U+00D1 LATIN CAPITAL LETTER N WITH TILDE */
        XK_Ograve:                      0x00d2,

        /* U+00D2 LATIN CAPITAL LETTER O WITH GRAVE */
        XK_Oacute:                      0x00d3,

        /* U+00D3 LATIN CAPITAL LETTER O WITH ACUTE */
        XK_Ocircumflex:                 0x00d4,

        /* U+00D4 LATIN CAPITAL LETTER O WITH CIRCUMFLEX */
        XK_Otilde:                      0x00d5,

        /* U+00D5 LATIN CAPITAL LETTER O WITH TILDE */
        XK_Odiaeresis:                  0x00d6,

        /* U+00D6 LATIN CAPITAL LETTER O WITH DIAERESIS */
        XK_multiply:                    0x00d7,

        /* U+00D7 MULTIPLICATION SIGN */
        XK_Oslash:                      0x00d8,

        /* U+00D8 LATIN CAPITAL LETTER O WITH STROKE */
        XK_Ooblique:                    0x00d8,

        /* U+00D8 LATIN CAPITAL LETTER O WITH STROKE */
        XK_Ugrave:                      0x00d9,

        /* U+00D9 LATIN CAPITAL LETTER U WITH GRAVE */
        XK_Uacute:                      0x00da,

        /* U+00DA LATIN CAPITAL LETTER U WITH ACUTE */
        XK_Ucircumflex:                 0x00db,

        /* U+00DB LATIN CAPITAL LETTER U WITH CIRCUMFLEX */
        XK_Udiaeresis:                  0x00dc,

        /* U+00DC LATIN CAPITAL LETTER U WITH DIAERESIS */
        XK_Yacute:                      0x00dd,

        /* U+00DD LATIN CAPITAL LETTER Y WITH ACUTE */
        XK_THORN:                       0x00de,

        /* U+00DE LATIN CAPITAL LETTER THORN */
        XK_Thorn:                       0x00de,

        /* deprecated */
        XK_ssharp:                      0x00df,

        /* U+00DF LATIN SMALL LETTER SHARP S */
        XK_agrave:                      0x00e0,

        /* U+00E0 LATIN SMALL LETTER A WITH GRAVE */
        XK_aacute:                      0x00e1,

        /* U+00E1 LATIN SMALL LETTER A WITH ACUTE */
        XK_acircumflex:                 0x00e2,

        /* U+00E2 LATIN SMALL LETTER A WITH CIRCUMFLEX */
        XK_atilde:                      0x00e3,

        /* U+00E3 LATIN SMALL LETTER A WITH TILDE */
        XK_adiaeresis:                  0x00e4,

        /* U+00E4 LATIN SMALL LETTER A WITH DIAERESIS */
        XK_aring:                       0x00e5,

        /* U+00E5 LATIN SMALL LETTER A WITH RING ABOVE */
        XK_ae:                          0x00e6,

        /* U+00E6 LATIN SMALL LETTER AE */
        XK_ccedilla:                    0x00e7,

        /* U+00E7 LATIN SMALL LETTER C WITH CEDILLA */
        XK_egrave:                      0x00e8,

        /* U+00E8 LATIN SMALL LETTER E WITH GRAVE */
        XK_eacute:                      0x00e9,

        /* U+00E9 LATIN SMALL LETTER E WITH ACUTE */
        XK_ecircumflex:                 0x00ea,

        /* U+00EA LATIN SMALL LETTER E WITH CIRCUMFLEX */
        XK_ediaeresis:                  0x00eb,

        /* U+00EB LATIN SMALL LETTER E WITH DIAERESIS */
        XK_igrave:                      0x00ec,

        /* U+00EC LATIN SMALL LETTER I WITH GRAVE */
        XK_iacute:                      0x00ed,

        /* U+00ED LATIN SMALL LETTER I WITH ACUTE */
        XK_icircumflex:                 0x00ee,

        /* U+00EE LATIN SMALL LETTER I WITH CIRCUMFLEX */
        XK_idiaeresis:                  0x00ef,

        /* U+00EF LATIN SMALL LETTER I WITH DIAERESIS */
        XK_eth:                         0x00f0,

        /* U+00F0 LATIN SMALL LETTER ETH */
        XK_ntilde:                      0x00f1,

        /* U+00F1 LATIN SMALL LETTER N WITH TILDE */
        XK_ograve:                      0x00f2,

        /* U+00F2 LATIN SMALL LETTER O WITH GRAVE */
        XK_oacute:                      0x00f3,

        /* U+00F3 LATIN SMALL LETTER O WITH ACUTE */
        XK_ocircumflex:                 0x00f4,

        /* U+00F4 LATIN SMALL LETTER O WITH CIRCUMFLEX */
        XK_otilde:                      0x00f5,

        /* U+00F5 LATIN SMALL LETTER O WITH TILDE */
        XK_odiaeresis:                  0x00f6,

        /* U+00F6 LATIN SMALL LETTER O WITH DIAERESIS */
        XK_division:                    0x00f7,

        /* U+00F7 DIVISION SIGN */
        XK_oslash:                      0x00f8,

        /* U+00F8 LATIN SMALL LETTER O WITH STROKE */
        XK_ooblique:                    0x00f8,

        /* U+00F8 LATIN SMALL LETTER O WITH STROKE */
        XK_ugrave:                      0x00f9,

        /* U+00F9 LATIN SMALL LETTER U WITH GRAVE */
        XK_uacute:                      0x00fa,

        /* U+00FA LATIN SMALL LETTER U WITH ACUTE */
        XK_ucircumflex:                 0x00fb,

        /* U+00FB LATIN SMALL LETTER U WITH CIRCUMFLEX */
        XK_udiaeresis:                  0x00fc,

        /* U+00FC LATIN SMALL LETTER U WITH DIAERESIS */
        XK_yacute:                      0x00fd,

        /* U+00FD LATIN SMALL LETTER Y WITH ACUTE */
        XK_thorn:                       0x00fe,

        /* U+00FE LATIN SMALL LETTER THORN */
        XK_ydiaeresis:                  0x00ff,

        /* U+00FF LATIN SMALL LETTER Y WITH DIAERESIS */

        /*
         * Korean
         * Byte 3 = 0x0e
         */

        XK_Hangul:                      0xff31,

        /* Hangul start/stop(toggle) */
        XK_Hangul_Hanja:                0xff34,

        /* Start Hangul->Hanja Conversion */
        XK_Hangul_Jeonja:               0xff38,

        /* Jeonja mode */

        /*
         * XFree86 vendor specific keysyms.
         *
         * The XFree86 keysym range is 0x10080001 - 0x1008FFFF.
         */

        XF86XK_ModeLock:                0x1008FF01,

        XF86XK_MonBrightnessUp:         0x1008FF02,
        XF86XK_MonBrightnessDown:       0x1008FF03,
        XF86XK_KbdLightOnOff:           0x1008FF04,
        XF86XK_KbdBrightnessUp:         0x1008FF05,
        XF86XK_KbdBrightnessDown:       0x1008FF06,
        XF86XK_Standby:                 0x1008FF10,
        XF86XK_AudioLowerVolume:        0x1008FF11,
        XF86XK_AudioMute:               0x1008FF12,
        XF86XK_AudioRaiseVolume:        0x1008FF13,
        XF86XK_AudioPlay:               0x1008FF14,
        XF86XK_AudioStop:               0x1008FF15,
        XF86XK_AudioPrev:               0x1008FF16,
        XF86XK_AudioNext:               0x1008FF17,
        XF86XK_HomePage:                0x1008FF18,
        XF86XK_Mail:                    0x1008FF19,
        XF86XK_Start:                   0x1008FF1A,
        XF86XK_Search:                  0x1008FF1B,
        XF86XK_AudioRecord:             0x1008FF1C,
        XF86XK_Calculator:              0x1008FF1D,
        XF86XK_Memo:                    0x1008FF1E,
        XF86XK_ToDoList:                0x1008FF1F,
        XF86XK_Calendar:                0x1008FF20,
        XF86XK_PowerDown:               0x1008FF21,
        XF86XK_ContrastAdjust:          0x1008FF22,
        XF86XK_RockerUp:                0x1008FF23,
        XF86XK_RockerDown:              0x1008FF24,
        XF86XK_RockerEnter:             0x1008FF25,
        XF86XK_Back:                    0x1008FF26,
        XF86XK_Forward:                 0x1008FF27,
        XF86XK_Stop:                    0x1008FF28,
        XF86XK_Refresh:                 0x1008FF29,
        XF86XK_PowerOff:                0x1008FF2A,
        XF86XK_WakeUp:                  0x1008FF2B,
        XF86XK_Eject:                   0x1008FF2C,
        XF86XK_ScreenSaver:             0x1008FF2D,
        XF86XK_WWW:                     0x1008FF2E,
        XF86XK_Sleep:                   0x1008FF2F,
        XF86XK_Favorites:               0x1008FF30,
        XF86XK_AudioPause:              0x1008FF31,
        XF86XK_AudioMedia:              0x1008FF32,
        XF86XK_MyComputer:              0x1008FF33,
        XF86XK_VendorHome:              0x1008FF34,
        XF86XK_LightBulb:               0x1008FF35,
        XF86XK_Shop:                    0x1008FF36,
        XF86XK_History:                 0x1008FF37,
        XF86XK_OpenURL:                 0x1008FF38,
        XF86XK_AddFavorite:             0x1008FF39,
        XF86XK_HotLinks:                0x1008FF3A,
        XF86XK_BrightnessAdjust:        0x1008FF3B,
        XF86XK_Finance:                 0x1008FF3C,
        XF86XK_Community:               0x1008FF3D,
        XF86XK_AudioRewind:             0x1008FF3E,
        XF86XK_BackForward:             0x1008FF3F,
        XF86XK_Launch0:                 0x1008FF40,
        XF86XK_Launch1:                 0x1008FF41,
        XF86XK_Launch2:                 0x1008FF42,
        XF86XK_Launch3:                 0x1008FF43,
        XF86XK_Launch4:                 0x1008FF44,
        XF86XK_Launch5:                 0x1008FF45,
        XF86XK_Launch6:                 0x1008FF46,
        XF86XK_Launch7:                 0x1008FF47,
        XF86XK_Launch8:                 0x1008FF48,
        XF86XK_Launch9:                 0x1008FF49,
        XF86XK_LaunchA:                 0x1008FF4A,
        XF86XK_LaunchB:                 0x1008FF4B,
        XF86XK_LaunchC:                 0x1008FF4C,
        XF86XK_LaunchD:                 0x1008FF4D,
        XF86XK_LaunchE:                 0x1008FF4E,
        XF86XK_LaunchF:                 0x1008FF4F,
        XF86XK_ApplicationLeft:         0x1008FF50,
        XF86XK_ApplicationRight:        0x1008FF51,
        XF86XK_Book:                    0x1008FF52,
        XF86XK_CD:                      0x1008FF53,
        XF86XK_Calculater:              0x1008FF54,
        XF86XK_Clear:                   0x1008FF55,
        XF86XK_Close:                   0x1008FF56,
        XF86XK_Copy:                    0x1008FF57,
        XF86XK_Cut:                     0x1008FF58,
        XF86XK_Display:                 0x1008FF59,
        XF86XK_DOS:                     0x1008FF5A,
        XF86XK_Documents:               0x1008FF5B,
        XF86XK_Excel:                   0x1008FF5C,
        XF86XK_Explorer:                0x1008FF5D,
        XF86XK_Game:                    0x1008FF5E,
        XF86XK_Go:                      0x1008FF5F,
        XF86XK_iTouch:                  0x1008FF60,
        XF86XK_LogOff:                  0x1008FF61,
        XF86XK_Market:                  0x1008FF62,
        XF86XK_Meeting:                 0x1008FF63,
        XF86XK_MenuKB:                  0x1008FF65,
        XF86XK_MenuPB:                  0x1008FF66,
        XF86XK_MySites:                 0x1008FF67,
        XF86XK_New:                     0x1008FF68,
        XF86XK_News:                    0x1008FF69,
        XF86XK_OfficeHome:              0x1008FF6A,
        XF86XK_Open:                    0x1008FF6B,
        XF86XK_Option:                  0x1008FF6C,
        XF86XK_Paste:                   0x1008FF6D,
        XF86XK_Phone:                   0x1008FF6E,
        XF86XK_Q:                       0x1008FF70,
        XF86XK_Reply:                   0x1008FF72,
        XF86XK_Reload:                  0x1008FF73,
        XF86XK_RotateWindows:           0x1008FF74,
        XF86XK_RotationPB:              0x1008FF75,
        XF86XK_RotationKB:              0x1008FF76,
        XF86XK_Save:                    0x1008FF77,
        XF86XK_ScrollUp:                0x1008FF78,
        XF86XK_ScrollDown:              0x1008FF79,
        XF86XK_ScrollClick:             0x1008FF7A,
        XF86XK_Send:                    0x1008FF7B,
        XF86XK_Spell:                   0x1008FF7C,
        XF86XK_SplitScreen:             0x1008FF7D,
        XF86XK_Support:                 0x1008FF7E,
        XF86XK_TaskPane:                0x1008FF7F,
        XF86XK_Terminal:                0x1008FF80,
        XF86XK_Tools:                   0x1008FF81,
        XF86XK_Travel:                  0x1008FF82,
        XF86XK_UserPB:                  0x1008FF84,
        XF86XK_User1KB:                 0x1008FF85,
        XF86XK_User2KB:                 0x1008FF86,
        XF86XK_Video:                   0x1008FF87,
        XF86XK_WheelButton:             0x1008FF88,
        XF86XK_Word:                    0x1008FF89,
        XF86XK_Xfer:                    0x1008FF8A,
        XF86XK_ZoomIn:                  0x1008FF8B,
        XF86XK_ZoomOut:                 0x1008FF8C,
        XF86XK_Away:                    0x1008FF8D,
        XF86XK_Messenger:               0x1008FF8E,
        XF86XK_WebCam:                  0x1008FF8F,
        XF86XK_MailForward:             0x1008FF90,
        XF86XK_Pictures:                0x1008FF91,
        XF86XK_Music:                   0x1008FF92,
        XF86XK_Battery:                 0x1008FF93,
        XF86XK_Bluetooth:               0x1008FF94,
        XF86XK_WLAN:                    0x1008FF95,
        XF86XK_UWB:                     0x1008FF96,
        XF86XK_AudioForward:            0x1008FF97,
        XF86XK_AudioRepeat:             0x1008FF98,
        XF86XK_AudioRandomPlay:         0x1008FF99,
        XF86XK_Subtitle:                0x1008FF9A,
        XF86XK_AudioCycleTrack:         0x1008FF9B,
        XF86XK_CycleAngle:              0x1008FF9C,
        XF86XK_FrameBack:               0x1008FF9D,
        XF86XK_FrameForward:            0x1008FF9E,
        XF86XK_Time:                    0x1008FF9F,
        XF86XK_Select:                  0x1008FFA0,
        XF86XK_View:                    0x1008FFA1,
        XF86XK_TopMenu:                 0x1008FFA2,
        XF86XK_Red:                     0x1008FFA3,
        XF86XK_Green:                   0x1008FFA4,
        XF86XK_Yellow:                  0x1008FFA5,
        XF86XK_Blue:                    0x1008FFA6,
        XF86XK_Suspend:                 0x1008FFA7,
        XF86XK_Hibernate:               0x1008FFA8,
        XF86XK_TouchpadToggle:          0x1008FFA9,
        XF86XK_TouchpadOn:              0x1008FFB0,
        XF86XK_TouchpadOff:             0x1008FFB1,
        XF86XK_AudioMicMute:            0x1008FFB2,
        XF86XK_Switch_VT_1:             0x1008FE01,
        XF86XK_Switch_VT_2:             0x1008FE02,
        XF86XK_Switch_VT_3:             0x1008FE03,
        XF86XK_Switch_VT_4:             0x1008FE04,
        XF86XK_Switch_VT_5:             0x1008FE05,
        XF86XK_Switch_VT_6:             0x1008FE06,
        XF86XK_Switch_VT_7:             0x1008FE07,
        XF86XK_Switch_VT_8:             0x1008FE08,
        XF86XK_Switch_VT_9:             0x1008FE09,
        XF86XK_Switch_VT_10:            0x1008FE0A,
        XF86XK_Switch_VT_11:            0x1008FE0B,
        XF86XK_Switch_VT_12:            0x1008FE0C,
        XF86XK_Ungrab:                  0x1008FE20,
        XF86XK_ClearGrab:               0x1008FE21,
        XF86XK_Next_VMode:              0x1008FE22,
        XF86XK_Prev_VMode:              0x1008FE23,
        XF86XK_LogWindowTree:           0x1008FE24,
        XF86XK_LogGrabInfo:             0x1008FE25
    };

    /*
     * Mapping from Unicode codepoints to X11/RFB keysyms
     *
     * This file was automatically generated from keysymdef.h
     * DO NOT EDIT!
     */

    /* Functions at the bottom */

    const $$$core$input$keysymdef$$codepoints = {
        0x0100: 0x03c0, // XK_Amacron
        0x0101: 0x03e0, // XK_amacron
        0x0102: 0x01c3, // XK_Abreve
        0x0103: 0x01e3, // XK_abreve
        0x0104: 0x01a1, // XK_Aogonek
        0x0105: 0x01b1, // XK_aogonek
        0x0106: 0x01c6, // XK_Cacute
        0x0107: 0x01e6, // XK_cacute
        0x0108: 0x02c6, // XK_Ccircumflex
        0x0109: 0x02e6, // XK_ccircumflex
        0x010a: 0x02c5, // XK_Cabovedot
        0x010b: 0x02e5, // XK_cabovedot
        0x010c: 0x01c8, // XK_Ccaron
        0x010d: 0x01e8, // XK_ccaron
        0x010e: 0x01cf, // XK_Dcaron
        0x010f: 0x01ef, // XK_dcaron
        0x0110: 0x01d0, // XK_Dstroke
        0x0111: 0x01f0, // XK_dstroke
        0x0112: 0x03aa, // XK_Emacron
        0x0113: 0x03ba, // XK_emacron
        0x0116: 0x03cc, // XK_Eabovedot
        0x0117: 0x03ec, // XK_eabovedot
        0x0118: 0x01ca, // XK_Eogonek
        0x0119: 0x01ea, // XK_eogonek
        0x011a: 0x01cc, // XK_Ecaron
        0x011b: 0x01ec, // XK_ecaron
        0x011c: 0x02d8, // XK_Gcircumflex
        0x011d: 0x02f8, // XK_gcircumflex
        0x011e: 0x02ab, // XK_Gbreve
        0x011f: 0x02bb, // XK_gbreve
        0x0120: 0x02d5, // XK_Gabovedot
        0x0121: 0x02f5, // XK_gabovedot
        0x0122: 0x03ab, // XK_Gcedilla
        0x0123: 0x03bb, // XK_gcedilla
        0x0124: 0x02a6, // XK_Hcircumflex
        0x0125: 0x02b6, // XK_hcircumflex
        0x0126: 0x02a1, // XK_Hstroke
        0x0127: 0x02b1, // XK_hstroke
        0x0128: 0x03a5, // XK_Itilde
        0x0129: 0x03b5, // XK_itilde
        0x012a: 0x03cf, // XK_Imacron
        0x012b: 0x03ef, // XK_imacron
        0x012e: 0x03c7, // XK_Iogonek
        0x012f: 0x03e7, // XK_iogonek
        0x0130: 0x02a9, // XK_Iabovedot
        0x0131: 0x02b9, // XK_idotless
        0x0134: 0x02ac, // XK_Jcircumflex
        0x0135: 0x02bc, // XK_jcircumflex
        0x0136: 0x03d3, // XK_Kcedilla
        0x0137: 0x03f3, // XK_kcedilla
        0x0138: 0x03a2, // XK_kra
        0x0139: 0x01c5, // XK_Lacute
        0x013a: 0x01e5, // XK_lacute
        0x013b: 0x03a6, // XK_Lcedilla
        0x013c: 0x03b6, // XK_lcedilla
        0x013d: 0x01a5, // XK_Lcaron
        0x013e: 0x01b5, // XK_lcaron
        0x0141: 0x01a3, // XK_Lstroke
        0x0142: 0x01b3, // XK_lstroke
        0x0143: 0x01d1, // XK_Nacute
        0x0144: 0x01f1, // XK_nacute
        0x0145: 0x03d1, // XK_Ncedilla
        0x0146: 0x03f1, // XK_ncedilla
        0x0147: 0x01d2, // XK_Ncaron
        0x0148: 0x01f2, // XK_ncaron
        0x014a: 0x03bd, // XK_ENG
        0x014b: 0x03bf, // XK_eng
        0x014c: 0x03d2, // XK_Omacron
        0x014d: 0x03f2, // XK_omacron
        0x0150: 0x01d5, // XK_Odoubleacute
        0x0151: 0x01f5, // XK_odoubleacute
        0x0152: 0x13bc, // XK_OE
        0x0153: 0x13bd, // XK_oe
        0x0154: 0x01c0, // XK_Racute
        0x0155: 0x01e0, // XK_racute
        0x0156: 0x03a3, // XK_Rcedilla
        0x0157: 0x03b3, // XK_rcedilla
        0x0158: 0x01d8, // XK_Rcaron
        0x0159: 0x01f8, // XK_rcaron
        0x015a: 0x01a6, // XK_Sacute
        0x015b: 0x01b6, // XK_sacute
        0x015c: 0x02de, // XK_Scircumflex
        0x015d: 0x02fe, // XK_scircumflex
        0x015e: 0x01aa, // XK_Scedilla
        0x015f: 0x01ba, // XK_scedilla
        0x0160: 0x01a9, // XK_Scaron
        0x0161: 0x01b9, // XK_scaron
        0x0162: 0x01de, // XK_Tcedilla
        0x0163: 0x01fe, // XK_tcedilla
        0x0164: 0x01ab, // XK_Tcaron
        0x0165: 0x01bb, // XK_tcaron
        0x0166: 0x03ac, // XK_Tslash
        0x0167: 0x03bc, // XK_tslash
        0x0168: 0x03dd, // XK_Utilde
        0x0169: 0x03fd, // XK_utilde
        0x016a: 0x03de, // XK_Umacron
        0x016b: 0x03fe, // XK_umacron
        0x016c: 0x02dd, // XK_Ubreve
        0x016d: 0x02fd, // XK_ubreve
        0x016e: 0x01d9, // XK_Uring
        0x016f: 0x01f9, // XK_uring
        0x0170: 0x01db, // XK_Udoubleacute
        0x0171: 0x01fb, // XK_udoubleacute
        0x0172: 0x03d9, // XK_Uogonek
        0x0173: 0x03f9, // XK_uogonek
        0x0178: 0x13be, // XK_Ydiaeresis
        0x0179: 0x01ac, // XK_Zacute
        0x017a: 0x01bc, // XK_zacute
        0x017b: 0x01af, // XK_Zabovedot
        0x017c: 0x01bf, // XK_zabovedot
        0x017d: 0x01ae, // XK_Zcaron
        0x017e: 0x01be, // XK_zcaron
        0x0192: 0x08f6, // XK_function
        0x01d2: 0x10001d1, // XK_Ocaron
        0x02c7: 0x01b7, // XK_caron
        0x02d8: 0x01a2, // XK_breve
        0x02d9: 0x01ff, // XK_abovedot
        0x02db: 0x01b2, // XK_ogonek
        0x02dd: 0x01bd, // XK_doubleacute
        0x0385: 0x07ae, // XK_Greek_accentdieresis
        0x0386: 0x07a1, // XK_Greek_ALPHAaccent
        0x0388: 0x07a2, // XK_Greek_EPSILONaccent
        0x0389: 0x07a3, // XK_Greek_ETAaccent
        0x038a: 0x07a4, // XK_Greek_IOTAaccent
        0x038c: 0x07a7, // XK_Greek_OMICRONaccent
        0x038e: 0x07a8, // XK_Greek_UPSILONaccent
        0x038f: 0x07ab, // XK_Greek_OMEGAaccent
        0x0390: 0x07b6, // XK_Greek_iotaaccentdieresis
        0x0391: 0x07c1, // XK_Greek_ALPHA
        0x0392: 0x07c2, // XK_Greek_BETA
        0x0393: 0x07c3, // XK_Greek_GAMMA
        0x0394: 0x07c4, // XK_Greek_DELTA
        0x0395: 0x07c5, // XK_Greek_EPSILON
        0x0396: 0x07c6, // XK_Greek_ZETA
        0x0397: 0x07c7, // XK_Greek_ETA
        0x0398: 0x07c8, // XK_Greek_THETA
        0x0399: 0x07c9, // XK_Greek_IOTA
        0x039a: 0x07ca, // XK_Greek_KAPPA
        0x039b: 0x07cb, // XK_Greek_LAMDA
        0x039c: 0x07cc, // XK_Greek_MU
        0x039d: 0x07cd, // XK_Greek_NU
        0x039e: 0x07ce, // XK_Greek_XI
        0x039f: 0x07cf, // XK_Greek_OMICRON
        0x03a0: 0x07d0, // XK_Greek_PI
        0x03a1: 0x07d1, // XK_Greek_RHO
        0x03a3: 0x07d2, // XK_Greek_SIGMA
        0x03a4: 0x07d4, // XK_Greek_TAU
        0x03a5: 0x07d5, // XK_Greek_UPSILON
        0x03a6: 0x07d6, // XK_Greek_PHI
        0x03a7: 0x07d7, // XK_Greek_CHI
        0x03a8: 0x07d8, // XK_Greek_PSI
        0x03a9: 0x07d9, // XK_Greek_OMEGA
        0x03aa: 0x07a5, // XK_Greek_IOTAdieresis
        0x03ab: 0x07a9, // XK_Greek_UPSILONdieresis
        0x03ac: 0x07b1, // XK_Greek_alphaaccent
        0x03ad: 0x07b2, // XK_Greek_epsilonaccent
        0x03ae: 0x07b3, // XK_Greek_etaaccent
        0x03af: 0x07b4, // XK_Greek_iotaaccent
        0x03b0: 0x07ba, // XK_Greek_upsilonaccentdieresis
        0x03b1: 0x07e1, // XK_Greek_alpha
        0x03b2: 0x07e2, // XK_Greek_beta
        0x03b3: 0x07e3, // XK_Greek_gamma
        0x03b4: 0x07e4, // XK_Greek_delta
        0x03b5: 0x07e5, // XK_Greek_epsilon
        0x03b6: 0x07e6, // XK_Greek_zeta
        0x03b7: 0x07e7, // XK_Greek_eta
        0x03b8: 0x07e8, // XK_Greek_theta
        0x03b9: 0x07e9, // XK_Greek_iota
        0x03ba: 0x07ea, // XK_Greek_kappa
        0x03bb: 0x07eb, // XK_Greek_lamda
        0x03bc: 0x07ec, // XK_Greek_mu
        0x03bd: 0x07ed, // XK_Greek_nu
        0x03be: 0x07ee, // XK_Greek_xi
        0x03bf: 0x07ef, // XK_Greek_omicron
        0x03c0: 0x07f0, // XK_Greek_pi
        0x03c1: 0x07f1, // XK_Greek_rho
        0x03c2: 0x07f3, // XK_Greek_finalsmallsigma
        0x03c3: 0x07f2, // XK_Greek_sigma
        0x03c4: 0x07f4, // XK_Greek_tau
        0x03c5: 0x07f5, // XK_Greek_upsilon
        0x03c6: 0x07f6, // XK_Greek_phi
        0x03c7: 0x07f7, // XK_Greek_chi
        0x03c8: 0x07f8, // XK_Greek_psi
        0x03c9: 0x07f9, // XK_Greek_omega
        0x03ca: 0x07b5, // XK_Greek_iotadieresis
        0x03cb: 0x07b9, // XK_Greek_upsilondieresis
        0x03cc: 0x07b7, // XK_Greek_omicronaccent
        0x03cd: 0x07b8, // XK_Greek_upsilonaccent
        0x03ce: 0x07bb, // XK_Greek_omegaaccent
        0x0401: 0x06b3, // XK_Cyrillic_IO
        0x0402: 0x06b1, // XK_Serbian_DJE
        0x0403: 0x06b2, // XK_Macedonia_GJE
        0x0404: 0x06b4, // XK_Ukrainian_IE
        0x0405: 0x06b5, // XK_Macedonia_DSE
        0x0406: 0x06b6, // XK_Ukrainian_I
        0x0407: 0x06b7, // XK_Ukrainian_YI
        0x0408: 0x06b8, // XK_Cyrillic_JE
        0x0409: 0x06b9, // XK_Cyrillic_LJE
        0x040a: 0x06ba, // XK_Cyrillic_NJE
        0x040b: 0x06bb, // XK_Serbian_TSHE
        0x040c: 0x06bc, // XK_Macedonia_KJE
        0x040e: 0x06be, // XK_Byelorussian_SHORTU
        0x040f: 0x06bf, // XK_Cyrillic_DZHE
        0x0410: 0x06e1, // XK_Cyrillic_A
        0x0411: 0x06e2, // XK_Cyrillic_BE
        0x0412: 0x06f7, // XK_Cyrillic_VE
        0x0413: 0x06e7, // XK_Cyrillic_GHE
        0x0414: 0x06e4, // XK_Cyrillic_DE
        0x0415: 0x06e5, // XK_Cyrillic_IE
        0x0416: 0x06f6, // XK_Cyrillic_ZHE
        0x0417: 0x06fa, // XK_Cyrillic_ZE
        0x0418: 0x06e9, // XK_Cyrillic_I
        0x0419: 0x06ea, // XK_Cyrillic_SHORTI
        0x041a: 0x06eb, // XK_Cyrillic_KA
        0x041b: 0x06ec, // XK_Cyrillic_EL
        0x041c: 0x06ed, // XK_Cyrillic_EM
        0x041d: 0x06ee, // XK_Cyrillic_EN
        0x041e: 0x06ef, // XK_Cyrillic_O
        0x041f: 0x06f0, // XK_Cyrillic_PE
        0x0420: 0x06f2, // XK_Cyrillic_ER
        0x0421: 0x06f3, // XK_Cyrillic_ES
        0x0422: 0x06f4, // XK_Cyrillic_TE
        0x0423: 0x06f5, // XK_Cyrillic_U
        0x0424: 0x06e6, // XK_Cyrillic_EF
        0x0425: 0x06e8, // XK_Cyrillic_HA
        0x0426: 0x06e3, // XK_Cyrillic_TSE
        0x0427: 0x06fe, // XK_Cyrillic_CHE
        0x0428: 0x06fb, // XK_Cyrillic_SHA
        0x0429: 0x06fd, // XK_Cyrillic_SHCHA
        0x042a: 0x06ff, // XK_Cyrillic_HARDSIGN
        0x042b: 0x06f9, // XK_Cyrillic_YERU
        0x042c: 0x06f8, // XK_Cyrillic_SOFTSIGN
        0x042d: 0x06fc, // XK_Cyrillic_E
        0x042e: 0x06e0, // XK_Cyrillic_YU
        0x042f: 0x06f1, // XK_Cyrillic_YA
        0x0430: 0x06c1, // XK_Cyrillic_a
        0x0431: 0x06c2, // XK_Cyrillic_be
        0x0432: 0x06d7, // XK_Cyrillic_ve
        0x0433: 0x06c7, // XK_Cyrillic_ghe
        0x0434: 0x06c4, // XK_Cyrillic_de
        0x0435: 0x06c5, // XK_Cyrillic_ie
        0x0436: 0x06d6, // XK_Cyrillic_zhe
        0x0437: 0x06da, // XK_Cyrillic_ze
        0x0438: 0x06c9, // XK_Cyrillic_i
        0x0439: 0x06ca, // XK_Cyrillic_shorti
        0x043a: 0x06cb, // XK_Cyrillic_ka
        0x043b: 0x06cc, // XK_Cyrillic_el
        0x043c: 0x06cd, // XK_Cyrillic_em
        0x043d: 0x06ce, // XK_Cyrillic_en
        0x043e: 0x06cf, // XK_Cyrillic_o
        0x043f: 0x06d0, // XK_Cyrillic_pe
        0x0440: 0x06d2, // XK_Cyrillic_er
        0x0441: 0x06d3, // XK_Cyrillic_es
        0x0442: 0x06d4, // XK_Cyrillic_te
        0x0443: 0x06d5, // XK_Cyrillic_u
        0x0444: 0x06c6, // XK_Cyrillic_ef
        0x0445: 0x06c8, // XK_Cyrillic_ha
        0x0446: 0x06c3, // XK_Cyrillic_tse
        0x0447: 0x06de, // XK_Cyrillic_che
        0x0448: 0x06db, // XK_Cyrillic_sha
        0x0449: 0x06dd, // XK_Cyrillic_shcha
        0x044a: 0x06df, // XK_Cyrillic_hardsign
        0x044b: 0x06d9, // XK_Cyrillic_yeru
        0x044c: 0x06d8, // XK_Cyrillic_softsign
        0x044d: 0x06dc, // XK_Cyrillic_e
        0x044e: 0x06c0, // XK_Cyrillic_yu
        0x044f: 0x06d1, // XK_Cyrillic_ya
        0x0451: 0x06a3, // XK_Cyrillic_io
        0x0452: 0x06a1, // XK_Serbian_dje
        0x0453: 0x06a2, // XK_Macedonia_gje
        0x0454: 0x06a4, // XK_Ukrainian_ie
        0x0455: 0x06a5, // XK_Macedonia_dse
        0x0456: 0x06a6, // XK_Ukrainian_i
        0x0457: 0x06a7, // XK_Ukrainian_yi
        0x0458: 0x06a8, // XK_Cyrillic_je
        0x0459: 0x06a9, // XK_Cyrillic_lje
        0x045a: 0x06aa, // XK_Cyrillic_nje
        0x045b: 0x06ab, // XK_Serbian_tshe
        0x045c: 0x06ac, // XK_Macedonia_kje
        0x045e: 0x06ae, // XK_Byelorussian_shortu
        0x045f: 0x06af, // XK_Cyrillic_dzhe
        0x0490: 0x06bd, // XK_Ukrainian_GHE_WITH_UPTURN
        0x0491: 0x06ad, // XK_Ukrainian_ghe_with_upturn
        0x05d0: 0x0ce0, // XK_hebrew_aleph
        0x05d1: 0x0ce1, // XK_hebrew_bet
        0x05d2: 0x0ce2, // XK_hebrew_gimel
        0x05d3: 0x0ce3, // XK_hebrew_dalet
        0x05d4: 0x0ce4, // XK_hebrew_he
        0x05d5: 0x0ce5, // XK_hebrew_waw
        0x05d6: 0x0ce6, // XK_hebrew_zain
        0x05d7: 0x0ce7, // XK_hebrew_chet
        0x05d8: 0x0ce8, // XK_hebrew_tet
        0x05d9: 0x0ce9, // XK_hebrew_yod
        0x05da: 0x0cea, // XK_hebrew_finalkaph
        0x05db: 0x0ceb, // XK_hebrew_kaph
        0x05dc: 0x0cec, // XK_hebrew_lamed
        0x05dd: 0x0ced, // XK_hebrew_finalmem
        0x05de: 0x0cee, // XK_hebrew_mem
        0x05df: 0x0cef, // XK_hebrew_finalnun
        0x05e0: 0x0cf0, // XK_hebrew_nun
        0x05e1: 0x0cf1, // XK_hebrew_samech
        0x05e2: 0x0cf2, // XK_hebrew_ayin
        0x05e3: 0x0cf3, // XK_hebrew_finalpe
        0x05e4: 0x0cf4, // XK_hebrew_pe
        0x05e5: 0x0cf5, // XK_hebrew_finalzade
        0x05e6: 0x0cf6, // XK_hebrew_zade
        0x05e7: 0x0cf7, // XK_hebrew_qoph
        0x05e8: 0x0cf8, // XK_hebrew_resh
        0x05e9: 0x0cf9, // XK_hebrew_shin
        0x05ea: 0x0cfa, // XK_hebrew_taw
        0x060c: 0x05ac, // XK_Arabic_comma
        0x061b: 0x05bb, // XK_Arabic_semicolon
        0x061f: 0x05bf, // XK_Arabic_question_mark
        0x0621: 0x05c1, // XK_Arabic_hamza
        0x0622: 0x05c2, // XK_Arabic_maddaonalef
        0x0623: 0x05c3, // XK_Arabic_hamzaonalef
        0x0624: 0x05c4, // XK_Arabic_hamzaonwaw
        0x0625: 0x05c5, // XK_Arabic_hamzaunderalef
        0x0626: 0x05c6, // XK_Arabic_hamzaonyeh
        0x0627: 0x05c7, // XK_Arabic_alef
        0x0628: 0x05c8, // XK_Arabic_beh
        0x0629: 0x05c9, // XK_Arabic_tehmarbuta
        0x062a: 0x05ca, // XK_Arabic_teh
        0x062b: 0x05cb, // XK_Arabic_theh
        0x062c: 0x05cc, // XK_Arabic_jeem
        0x062d: 0x05cd, // XK_Arabic_hah
        0x062e: 0x05ce, // XK_Arabic_khah
        0x062f: 0x05cf, // XK_Arabic_dal
        0x0630: 0x05d0, // XK_Arabic_thal
        0x0631: 0x05d1, // XK_Arabic_ra
        0x0632: 0x05d2, // XK_Arabic_zain
        0x0633: 0x05d3, // XK_Arabic_seen
        0x0634: 0x05d4, // XK_Arabic_sheen
        0x0635: 0x05d5, // XK_Arabic_sad
        0x0636: 0x05d6, // XK_Arabic_dad
        0x0637: 0x05d7, // XK_Arabic_tah
        0x0638: 0x05d8, // XK_Arabic_zah
        0x0639: 0x05d9, // XK_Arabic_ain
        0x063a: 0x05da, // XK_Arabic_ghain
        0x0640: 0x05e0, // XK_Arabic_tatweel
        0x0641: 0x05e1, // XK_Arabic_feh
        0x0642: 0x05e2, // XK_Arabic_qaf
        0x0643: 0x05e3, // XK_Arabic_kaf
        0x0644: 0x05e4, // XK_Arabic_lam
        0x0645: 0x05e5, // XK_Arabic_meem
        0x0646: 0x05e6, // XK_Arabic_noon
        0x0647: 0x05e7, // XK_Arabic_ha
        0x0648: 0x05e8, // XK_Arabic_waw
        0x0649: 0x05e9, // XK_Arabic_alefmaksura
        0x064a: 0x05ea, // XK_Arabic_yeh
        0x064b: 0x05eb, // XK_Arabic_fathatan
        0x064c: 0x05ec, // XK_Arabic_dammatan
        0x064d: 0x05ed, // XK_Arabic_kasratan
        0x064e: 0x05ee, // XK_Arabic_fatha
        0x064f: 0x05ef, // XK_Arabic_damma
        0x0650: 0x05f0, // XK_Arabic_kasra
        0x0651: 0x05f1, // XK_Arabic_shadda
        0x0652: 0x05f2, // XK_Arabic_sukun
        0x0e01: 0x0da1, // XK_Thai_kokai
        0x0e02: 0x0da2, // XK_Thai_khokhai
        0x0e03: 0x0da3, // XK_Thai_khokhuat
        0x0e04: 0x0da4, // XK_Thai_khokhwai
        0x0e05: 0x0da5, // XK_Thai_khokhon
        0x0e06: 0x0da6, // XK_Thai_khorakhang
        0x0e07: 0x0da7, // XK_Thai_ngongu
        0x0e08: 0x0da8, // XK_Thai_chochan
        0x0e09: 0x0da9, // XK_Thai_choching
        0x0e0a: 0x0daa, // XK_Thai_chochang
        0x0e0b: 0x0dab, // XK_Thai_soso
        0x0e0c: 0x0dac, // XK_Thai_chochoe
        0x0e0d: 0x0dad, // XK_Thai_yoying
        0x0e0e: 0x0dae, // XK_Thai_dochada
        0x0e0f: 0x0daf, // XK_Thai_topatak
        0x0e10: 0x0db0, // XK_Thai_thothan
        0x0e11: 0x0db1, // XK_Thai_thonangmontho
        0x0e12: 0x0db2, // XK_Thai_thophuthao
        0x0e13: 0x0db3, // XK_Thai_nonen
        0x0e14: 0x0db4, // XK_Thai_dodek
        0x0e15: 0x0db5, // XK_Thai_totao
        0x0e16: 0x0db6, // XK_Thai_thothung
        0x0e17: 0x0db7, // XK_Thai_thothahan
        0x0e18: 0x0db8, // XK_Thai_thothong
        0x0e19: 0x0db9, // XK_Thai_nonu
        0x0e1a: 0x0dba, // XK_Thai_bobaimai
        0x0e1b: 0x0dbb, // XK_Thai_popla
        0x0e1c: 0x0dbc, // XK_Thai_phophung
        0x0e1d: 0x0dbd, // XK_Thai_fofa
        0x0e1e: 0x0dbe, // XK_Thai_phophan
        0x0e1f: 0x0dbf, // XK_Thai_fofan
        0x0e20: 0x0dc0, // XK_Thai_phosamphao
        0x0e21: 0x0dc1, // XK_Thai_moma
        0x0e22: 0x0dc2, // XK_Thai_yoyak
        0x0e23: 0x0dc3, // XK_Thai_rorua
        0x0e24: 0x0dc4, // XK_Thai_ru
        0x0e25: 0x0dc5, // XK_Thai_loling
        0x0e26: 0x0dc6, // XK_Thai_lu
        0x0e27: 0x0dc7, // XK_Thai_wowaen
        0x0e28: 0x0dc8, // XK_Thai_sosala
        0x0e29: 0x0dc9, // XK_Thai_sorusi
        0x0e2a: 0x0dca, // XK_Thai_sosua
        0x0e2b: 0x0dcb, // XK_Thai_hohip
        0x0e2c: 0x0dcc, // XK_Thai_lochula
        0x0e2d: 0x0dcd, // XK_Thai_oang
        0x0e2e: 0x0dce, // XK_Thai_honokhuk
        0x0e2f: 0x0dcf, // XK_Thai_paiyannoi
        0x0e30: 0x0dd0, // XK_Thai_saraa
        0x0e31: 0x0dd1, // XK_Thai_maihanakat
        0x0e32: 0x0dd2, // XK_Thai_saraaa
        0x0e33: 0x0dd3, // XK_Thai_saraam
        0x0e34: 0x0dd4, // XK_Thai_sarai
        0x0e35: 0x0dd5, // XK_Thai_saraii
        0x0e36: 0x0dd6, // XK_Thai_saraue
        0x0e37: 0x0dd7, // XK_Thai_sarauee
        0x0e38: 0x0dd8, // XK_Thai_sarau
        0x0e39: 0x0dd9, // XK_Thai_sarauu
        0x0e3a: 0x0dda, // XK_Thai_phinthu
        0x0e3f: 0x0ddf, // XK_Thai_baht
        0x0e40: 0x0de0, // XK_Thai_sarae
        0x0e41: 0x0de1, // XK_Thai_saraae
        0x0e42: 0x0de2, // XK_Thai_sarao
        0x0e43: 0x0de3, // XK_Thai_saraaimaimuan
        0x0e44: 0x0de4, // XK_Thai_saraaimaimalai
        0x0e45: 0x0de5, // XK_Thai_lakkhangyao
        0x0e46: 0x0de6, // XK_Thai_maiyamok
        0x0e47: 0x0de7, // XK_Thai_maitaikhu
        0x0e48: 0x0de8, // XK_Thai_maiek
        0x0e49: 0x0de9, // XK_Thai_maitho
        0x0e4a: 0x0dea, // XK_Thai_maitri
        0x0e4b: 0x0deb, // XK_Thai_maichattawa
        0x0e4c: 0x0dec, // XK_Thai_thanthakhat
        0x0e4d: 0x0ded, // XK_Thai_nikhahit
        0x0e50: 0x0df0, // XK_Thai_leksun
        0x0e51: 0x0df1, // XK_Thai_leknung
        0x0e52: 0x0df2, // XK_Thai_leksong
        0x0e53: 0x0df3, // XK_Thai_leksam
        0x0e54: 0x0df4, // XK_Thai_leksi
        0x0e55: 0x0df5, // XK_Thai_lekha
        0x0e56: 0x0df6, // XK_Thai_lekhok
        0x0e57: 0x0df7, // XK_Thai_lekchet
        0x0e58: 0x0df8, // XK_Thai_lekpaet
        0x0e59: 0x0df9, // XK_Thai_lekkao
        0x2002: 0x0aa2, // XK_enspace
        0x2003: 0x0aa1, // XK_emspace
        0x2004: 0x0aa3, // XK_em3space
        0x2005: 0x0aa4, // XK_em4space
        0x2007: 0x0aa5, // XK_digitspace
        0x2008: 0x0aa6, // XK_punctspace
        0x2009: 0x0aa7, // XK_thinspace
        0x200a: 0x0aa8, // XK_hairspace
        0x2012: 0x0abb, // XK_figdash
        0x2013: 0x0aaa, // XK_endash
        0x2014: 0x0aa9, // XK_emdash
        0x2015: 0x07af, // XK_Greek_horizbar
        0x2017: 0x0cdf, // XK_hebrew_doublelowline
        0x2018: 0x0ad0, // XK_leftsinglequotemark
        0x2019: 0x0ad1, // XK_rightsinglequotemark
        0x201a: 0x0afd, // XK_singlelowquotemark
        0x201c: 0x0ad2, // XK_leftdoublequotemark
        0x201d: 0x0ad3, // XK_rightdoublequotemark
        0x201e: 0x0afe, // XK_doublelowquotemark
        0x2020: 0x0af1, // XK_dagger
        0x2021: 0x0af2, // XK_doubledagger
        0x2022: 0x0ae6, // XK_enfilledcircbullet
        0x2025: 0x0aaf, // XK_doubbaselinedot
        0x2026: 0x0aae, // XK_ellipsis
        0x2030: 0x0ad5, // XK_permille
        0x2032: 0x0ad6, // XK_minutes
        0x2033: 0x0ad7, // XK_seconds
        0x2038: 0x0afc, // XK_caret
        0x203e: 0x047e, // XK_overline
        0x20a9: 0x0eff, // XK_Korean_Won
        0x20ac: 0x20ac, // XK_EuroSign
        0x2105: 0x0ab8, // XK_careof
        0x2116: 0x06b0, // XK_numerosign
        0x2117: 0x0afb, // XK_phonographcopyright
        0x211e: 0x0ad4, // XK_prescription
        0x2122: 0x0ac9, // XK_trademark
        0x2153: 0x0ab0, // XK_onethird
        0x2154: 0x0ab1, // XK_twothirds
        0x2155: 0x0ab2, // XK_onefifth
        0x2156: 0x0ab3, // XK_twofifths
        0x2157: 0x0ab4, // XK_threefifths
        0x2158: 0x0ab5, // XK_fourfifths
        0x2159: 0x0ab6, // XK_onesixth
        0x215a: 0x0ab7, // XK_fivesixths
        0x215b: 0x0ac3, // XK_oneeighth
        0x215c: 0x0ac4, // XK_threeeighths
        0x215d: 0x0ac5, // XK_fiveeighths
        0x215e: 0x0ac6, // XK_seveneighths
        0x2190: 0x08fb, // XK_leftarrow
        0x2191: 0x08fc, // XK_uparrow
        0x2192: 0x08fd, // XK_rightarrow
        0x2193: 0x08fe, // XK_downarrow
        0x21d2: 0x08ce, // XK_implies
        0x21d4: 0x08cd, // XK_ifonlyif
        0x2202: 0x08ef, // XK_partialderivative
        0x2207: 0x08c5, // XK_nabla
        0x2218: 0x0bca, // XK_jot
        0x221a: 0x08d6, // XK_radical
        0x221d: 0x08c1, // XK_variation
        0x221e: 0x08c2, // XK_infinity
        0x2227: 0x08de, // XK_logicaland
        0x2228: 0x08df, // XK_logicalor
        0x2229: 0x08dc, // XK_intersection
        0x222a: 0x08dd, // XK_union
        0x222b: 0x08bf, // XK_integral
        0x2234: 0x08c0, // XK_therefore
        0x223c: 0x08c8, // XK_approximate
        0x2243: 0x08c9, // XK_similarequal
        0x2245: 0x1002248, // XK_approxeq
        0x2260: 0x08bd, // XK_notequal
        0x2261: 0x08cf, // XK_identical
        0x2264: 0x08bc, // XK_lessthanequal
        0x2265: 0x08be, // XK_greaterthanequal
        0x2282: 0x08da, // XK_includedin
        0x2283: 0x08db, // XK_includes
        0x22a2: 0x0bfc, // XK_righttack
        0x22a3: 0x0bdc, // XK_lefttack
        0x22a4: 0x0bc2, // XK_downtack
        0x22a5: 0x0bce, // XK_uptack
        0x2308: 0x0bd3, // XK_upstile
        0x230a: 0x0bc4, // XK_downstile
        0x2315: 0x0afa, // XK_telephonerecorder
        0x2320: 0x08a4, // XK_topintegral
        0x2321: 0x08a5, // XK_botintegral
        0x2395: 0x0bcc, // XK_quad
        0x239b: 0x08ab, // XK_topleftparens
        0x239d: 0x08ac, // XK_botleftparens
        0x239e: 0x08ad, // XK_toprightparens
        0x23a0: 0x08ae, // XK_botrightparens
        0x23a1: 0x08a7, // XK_topleftsqbracket
        0x23a3: 0x08a8, // XK_botleftsqbracket
        0x23a4: 0x08a9, // XK_toprightsqbracket
        0x23a6: 0x08aa, // XK_botrightsqbracket
        0x23a8: 0x08af, // XK_leftmiddlecurlybrace
        0x23ac: 0x08b0, // XK_rightmiddlecurlybrace
        0x23b7: 0x08a1, // XK_leftradical
        0x23ba: 0x09ef, // XK_horizlinescan1
        0x23bb: 0x09f0, // XK_horizlinescan3
        0x23bc: 0x09f2, // XK_horizlinescan7
        0x23bd: 0x09f3, // XK_horizlinescan9
        0x2409: 0x09e2, // XK_ht
        0x240a: 0x09e5, // XK_lf
        0x240b: 0x09e9, // XK_vt
        0x240c: 0x09e3, // XK_ff
        0x240d: 0x09e4, // XK_cr
        0x2423: 0x0aac, // XK_signifblank
        0x2424: 0x09e8, // XK_nl
        0x2500: 0x08a3, // XK_horizconnector
        0x2502: 0x08a6, // XK_vertconnector
        0x250c: 0x08a2, // XK_topleftradical
        0x2510: 0x09eb, // XK_uprightcorner
        0x2514: 0x09ed, // XK_lowleftcorner
        0x2518: 0x09ea, // XK_lowrightcorner
        0x251c: 0x09f4, // XK_leftt
        0x2524: 0x09f5, // XK_rightt
        0x252c: 0x09f7, // XK_topt
        0x2534: 0x09f6, // XK_bott
        0x253c: 0x09ee, // XK_crossinglines
        0x2592: 0x09e1, // XK_checkerboard
        0x25aa: 0x0ae7, // XK_enfilledsqbullet
        0x25ab: 0x0ae1, // XK_enopensquarebullet
        0x25ac: 0x0adb, // XK_filledrectbullet
        0x25ad: 0x0ae2, // XK_openrectbullet
        0x25ae: 0x0adf, // XK_emfilledrect
        0x25af: 0x0acf, // XK_emopenrectangle
        0x25b2: 0x0ae8, // XK_filledtribulletup
        0x25b3: 0x0ae3, // XK_opentribulletup
        0x25b6: 0x0add, // XK_filledrighttribullet
        0x25b7: 0x0acd, // XK_rightopentriangle
        0x25bc: 0x0ae9, // XK_filledtribulletdown
        0x25bd: 0x0ae4, // XK_opentribulletdown
        0x25c0: 0x0adc, // XK_filledlefttribullet
        0x25c1: 0x0acc, // XK_leftopentriangle
        0x25c6: 0x09e0, // XK_soliddiamond
        0x25cb: 0x0ace, // XK_emopencircle
        0x25cf: 0x0ade, // XK_emfilledcircle
        0x25e6: 0x0ae0, // XK_enopencircbullet
        0x2606: 0x0ae5, // XK_openstar
        0x260e: 0x0af9, // XK_telephone
        0x2613: 0x0aca, // XK_signaturemark
        0x261c: 0x0aea, // XK_leftpointer
        0x261e: 0x0aeb, // XK_rightpointer
        0x2640: 0x0af8, // XK_femalesymbol
        0x2642: 0x0af7, // XK_malesymbol
        0x2663: 0x0aec, // XK_club
        0x2665: 0x0aee, // XK_heart
        0x2666: 0x0aed, // XK_diamond
        0x266d: 0x0af6, // XK_musicalflat
        0x266f: 0x0af5, // XK_musicalsharp
        0x2713: 0x0af3, // XK_checkmark
        0x2717: 0x0af4, // XK_ballotcross
        0x271d: 0x0ad9, // XK_latincross
        0x2720: 0x0af0, // XK_maltesecross
        0x27e8: 0x0abc, // XK_leftanglebracket
        0x27e9: 0x0abe, // XK_rightanglebracket
        0x3001: 0x04a4, // XK_kana_comma
        0x3002: 0x04a1, // XK_kana_fullstop
        0x300c: 0x04a2, // XK_kana_openingbracket
        0x300d: 0x04a3, // XK_kana_closingbracket
        0x309b: 0x04de, // XK_voicedsound
        0x309c: 0x04df, // XK_semivoicedsound
        0x30a1: 0x04a7, // XK_kana_a
        0x30a2: 0x04b1, // XK_kana_A
        0x30a3: 0x04a8, // XK_kana_i
        0x30a4: 0x04b2, // XK_kana_I
        0x30a5: 0x04a9, // XK_kana_u
        0x30a6: 0x04b3, // XK_kana_U
        0x30a7: 0x04aa, // XK_kana_e
        0x30a8: 0x04b4, // XK_kana_E
        0x30a9: 0x04ab, // XK_kana_o
        0x30aa: 0x04b5, // XK_kana_O
        0x30ab: 0x04b6, // XK_kana_KA
        0x30ad: 0x04b7, // XK_kana_KI
        0x30af: 0x04b8, // XK_kana_KU
        0x30b1: 0x04b9, // XK_kana_KE
        0x30b3: 0x04ba, // XK_kana_KO
        0x30b5: 0x04bb, // XK_kana_SA
        0x30b7: 0x04bc, // XK_kana_SHI
        0x30b9: 0x04bd, // XK_kana_SU
        0x30bb: 0x04be, // XK_kana_SE
        0x30bd: 0x04bf, // XK_kana_SO
        0x30bf: 0x04c0, // XK_kana_TA
        0x30c1: 0x04c1, // XK_kana_CHI
        0x30c3: 0x04af, // XK_kana_tsu
        0x30c4: 0x04c2, // XK_kana_TSU
        0x30c6: 0x04c3, // XK_kana_TE
        0x30c8: 0x04c4, // XK_kana_TO
        0x30ca: 0x04c5, // XK_kana_NA
        0x30cb: 0x04c6, // XK_kana_NI
        0x30cc: 0x04c7, // XK_kana_NU
        0x30cd: 0x04c8, // XK_kana_NE
        0x30ce: 0x04c9, // XK_kana_NO
        0x30cf: 0x04ca, // XK_kana_HA
        0x30d2: 0x04cb, // XK_kana_HI
        0x30d5: 0x04cc, // XK_kana_FU
        0x30d8: 0x04cd, // XK_kana_HE
        0x30db: 0x04ce, // XK_kana_HO
        0x30de: 0x04cf, // XK_kana_MA
        0x30df: 0x04d0, // XK_kana_MI
        0x30e0: 0x04d1, // XK_kana_MU
        0x30e1: 0x04d2, // XK_kana_ME
        0x30e2: 0x04d3, // XK_kana_MO
        0x30e3: 0x04ac, // XK_kana_ya
        0x30e4: 0x04d4, // XK_kana_YA
        0x30e5: 0x04ad, // XK_kana_yu
        0x30e6: 0x04d5, // XK_kana_YU
        0x30e7: 0x04ae, // XK_kana_yo
        0x30e8: 0x04d6, // XK_kana_YO
        0x30e9: 0x04d7, // XK_kana_RA
        0x30ea: 0x04d8, // XK_kana_RI
        0x30eb: 0x04d9, // XK_kana_RU
        0x30ec: 0x04da, // XK_kana_RE
        0x30ed: 0x04db, // XK_kana_RO
        0x30ef: 0x04dc, // XK_kana_WA
        0x30f2: 0x04a6, // XK_kana_WO
        0x30f3: 0x04dd, // XK_kana_N
        0x30fb: 0x04a5, // XK_kana_conjunctive
        0x30fc: 0x04b0, // XK_prolongedsound
    };

    var $$$core$input$keysymdef$$default = {
        lookup(u) {
            // Latin-1 is one-to-one mapping
            if ((u >= 0x20) && (u <= 0xff)) {
                return u;
            }

            // Lookup table (fairly random)
            const keysym = $$$core$input$keysymdef$$codepoints[u];
            if (keysym !== undefined) {
                return keysym;
            }

            // General mapping as final fallback
            return 0x01000000 | u;
        }
    };

    var $$vkeys$$default = {
        0x08: 'Backspace',
        0x09: 'Tab',
        0x0a: 'NumpadClear',

        // IE11 sends evt.keyCode: 12 when numlock is off
        0x0c: 'Numpad5',

        0x0d: 'Enter',
        0x10: 'ShiftLeft',
        0x11: 'ControlLeft',
        0x12: 'AltLeft',
        0x13: 'Pause',
        0x14: 'CapsLock',
        0x15: 'Lang1',
        0x19: 'Lang2',
        0x1b: 'Escape',
        0x1c: 'Convert',
        0x1d: 'NonConvert',
        0x20: 'Space',
        0x21: 'PageUp',
        0x22: 'PageDown',
        0x23: 'End',
        0x24: 'Home',
        0x25: 'ArrowLeft',
        0x26: 'ArrowUp',
        0x27: 'ArrowRight',
        0x28: 'ArrowDown',
        0x29: 'Select',
        0x2c: 'PrintScreen',
        0x2d: 'Insert',
        0x2e: 'Delete',
        0x2f: 'Help',
        0x30: 'Digit0',
        0x31: 'Digit1',
        0x32: 'Digit2',
        0x33: 'Digit3',
        0x34: 'Digit4',
        0x35: 'Digit5',
        0x36: 'Digit6',
        0x37: 'Digit7',
        0x38: 'Digit8',
        0x39: 'Digit9',
        0x5b: 'MetaLeft',
        0x5c: 'MetaRight',
        0x5d: 'ContextMenu',
        0x5f: 'Sleep',
        0x60: 'Numpad0',
        0x61: 'Numpad1',
        0x62: 'Numpad2',
        0x63: 'Numpad3',
        0x64: 'Numpad4',
        0x65: 'Numpad5',
        0x66: 'Numpad6',
        0x67: 'Numpad7',
        0x68: 'Numpad8',
        0x69: 'Numpad9',
        0x6a: 'NumpadMultiply',
        0x6b: 'NumpadAdd',
        0x6c: 'NumpadDecimal',
        0x6d: 'NumpadSubtract',

        // Duplicate, because buggy on Windows
        0x6e: 'NumpadDecimal',

        0x6f: 'NumpadDivide',
        0x70: 'F1',
        0x71: 'F2',
        0x72: 'F3',
        0x73: 'F4',
        0x74: 'F5',
        0x75: 'F6',
        0x76: 'F7',
        0x77: 'F8',
        0x78: 'F9',
        0x79: 'F10',
        0x7a: 'F11',
        0x7b: 'F12',
        0x7c: 'F13',
        0x7d: 'F14',
        0x7e: 'F15',
        0x7f: 'F16',
        0x80: 'F17',
        0x81: 'F18',
        0x82: 'F19',
        0x83: 'F20',
        0x84: 'F21',
        0x85: 'F22',
        0x86: 'F23',
        0x87: 'F24',
        0x90: 'NumLock',
        0x91: 'ScrollLock',
        0xa6: 'BrowserBack',
        0xa7: 'BrowserForward',
        0xa8: 'BrowserRefresh',
        0xa9: 'BrowserStop',
        0xaa: 'BrowserSearch',
        0xab: 'BrowserFavorites',
        0xac: 'BrowserHome',
        0xad: 'AudioVolumeMute',
        0xae: 'AudioVolumeDown',
        0xaf: 'AudioVolumeUp',
        0xb0: 'MediaTrackNext',
        0xb1: 'MediaTrackPrevious',
        0xb2: 'MediaStop',
        0xb3: 'MediaPlayPause',
        0xb4: 'LaunchMail',
        0xb5: 'MediaSelect',
        0xb6: 'LaunchApp1',
        0xb7: 'LaunchApp2',

        // Only when it is AltGraph
        0xe1: 'AltRight'
    };

    var $$fixedkeys$$default = {
        // 3.1.1.1. Writing System Keys

        'Backspace':        'Backspace',

        // 3.1.1.2. Functional Keys

        'AltLeft':          'Alt',

        // This could also be 'AltGraph'
        'AltRight':         'Alt',

        'CapsLock':         'CapsLock',
        'ContextMenu':      'ContextMenu',
        'ControlLeft':      'Control',
        'ControlRight':     'Control',
        'Enter':            'Enter',
        'MetaLeft':         'Meta',
        'MetaRight':        'Meta',
        'ShiftLeft':        'Shift',
        'ShiftRight':       'Shift',
        'Tab':              'Tab',

        // FIXME: Japanese/Korean keys

        // 3.1.2. Control Pad Section

        'Delete':           'Delete',

        'End':              'End',
        'Help':             'Help',
        'Home':             'Home',
        'Insert':           'Insert',
        'PageDown':         'PageDown',
        'PageUp':           'PageUp',

        // 3.1.3. Arrow Pad Section

        'ArrowDown':        'ArrowDown',

        'ArrowLeft':        'ArrowLeft',
        'ArrowRight':       'ArrowRight',
        'ArrowUp':          'ArrowUp',

        // 3.1.4. Numpad Section

        'NumLock':          'NumLock',

        'NumpadBackspace':  'Backspace',
        'NumpadClear':      'Clear',

        // 3.1.5. Function Section

        'Escape':           'Escape',

        'F1':               'F1',
        'F2':               'F2',
        'F3':               'F3',
        'F4':               'F4',
        'F5':               'F5',
        'F6':               'F6',
        'F7':               'F7',
        'F8':               'F8',
        'F9':               'F9',
        'F10':              'F10',
        'F11':              'F11',
        'F12':              'F12',
        'F13':              'F13',
        'F14':              'F14',
        'F15':              'F15',
        'F16':              'F16',
        'F17':              'F17',
        'F18':              'F18',
        'F19':              'F19',
        'F20':              'F20',
        'F21':              'F21',
        'F22':              'F22',
        'F23':              'F23',
        'F24':              'F24',
        'F25':              'F25',
        'F26':              'F26',
        'F27':              'F27',
        'F28':              'F28',
        'F29':              'F29',
        'F30':              'F30',
        'F31':              'F31',
        'F32':              'F32',
        'F33':              'F33',
        'F34':              'F34',
        'F35':              'F35',
        'PrintScreen':      'PrintScreen',
        'ScrollLock':       'ScrollLock',
        'Pause':            'Pause',

        // 3.1.6. Media Keys

        'BrowserBack':      'BrowserBack',

        'BrowserFavorites': 'BrowserFavorites',
        'BrowserForward':   'BrowserForward',
        'BrowserHome':      'BrowserHome',
        'BrowserRefresh':   'BrowserRefresh',
        'BrowserSearch':    'BrowserSearch',
        'BrowserStop':      'BrowserStop',
        'Eject':            'Eject',
        'LaunchApp1':       'LaunchMyComputer',
        'LaunchApp2':       'LaunchCalendar',
        'LaunchMail':       'LaunchMail',
        'MediaPlayPause':   'MediaPlay',
        'MediaStop':        'MediaStop',
        'MediaTrackNext':   'MediaTrackNext',
        'MediaTrackPrevious': 'MediaTrackPrevious',
        'Power':            'Power',
        'Sleep':            'Sleep',
        'AudioVolumeDown':  'AudioVolumeDown',
        'AudioVolumeMute':  'AudioVolumeMute',
        'AudioVolumeUp':    'AudioVolumeUp',
        'WakeUp':           'WakeUp'
    };

    /*
     * Mapping between HTML key values and VNC/X11 keysyms for "special"
     * keys that cannot be handled via their Unicode codepoint.
     *
     * See https://www.w3.org/TR/uievents-key/ for possible values.
     */

    const $$domkeytable$$DOMKeyTable = {};

    function $$domkeytable$$addStandard(key, standard) {
        if (standard === undefined) throw new Error("Undefined keysym for key \"" + key + "\"");
        if (key in $$domkeytable$$DOMKeyTable) throw new Error("Duplicate entry for key \"" + key + "\"");
        $$domkeytable$$DOMKeyTable[key] = [standard, standard, standard, standard];
    }

    function $$domkeytable$$addLeftRight(key, left, right) {
        if (left === undefined) throw new Error("Undefined keysym for key \"" + key + "\"");
        if (right === undefined) throw new Error("Undefined keysym for key \"" + key + "\"");
        if (key in $$domkeytable$$DOMKeyTable) throw new Error("Duplicate entry for key \"" + key + "\"");
        $$domkeytable$$DOMKeyTable[key] = [left, left, right, left];
    }

    function $$domkeytable$$addNumpad(key, standard, numpad) {
        if (standard === undefined) throw new Error("Undefined keysym for key \"" + key + "\"");
        if (numpad === undefined) throw new Error("Undefined keysym for key \"" + key + "\"");
        if (key in $$domkeytable$$DOMKeyTable) throw new Error("Duplicate entry for key \"" + key + "\"");
        $$domkeytable$$DOMKeyTable[key] = [standard, standard, standard, numpad];
    }

    // 2.2. Modifier Keys

    $$domkeytable$$addLeftRight("Alt", $$$core$input$keysym$$default.XK_Alt_L, $$$core$input$keysym$$default.XK_Alt_R);
    $$domkeytable$$addStandard("AltGraph", $$$core$input$keysym$$default.XK_ISO_Level3_Shift);
    $$domkeytable$$addStandard("CapsLock", $$$core$input$keysym$$default.XK_Caps_Lock);
    $$domkeytable$$addLeftRight("Control", $$$core$input$keysym$$default.XK_Control_L, $$$core$input$keysym$$default.XK_Control_R);
    // - Fn
    // - FnLock
    $$domkeytable$$addLeftRight("Hyper", $$$core$input$keysym$$default.XK_Super_L, $$$core$input$keysym$$default.XK_Super_R);
    $$domkeytable$$addLeftRight("Meta", $$$core$input$keysym$$default.XK_Super_L, $$$core$input$keysym$$default.XK_Super_R);
    $$domkeytable$$addStandard("NumLock", $$$core$input$keysym$$default.XK_Num_Lock);
    $$domkeytable$$addStandard("ScrollLock", $$$core$input$keysym$$default.XK_Scroll_Lock);
    $$domkeytable$$addLeftRight("Shift", $$$core$input$keysym$$default.XK_Shift_L, $$$core$input$keysym$$default.XK_Shift_R);
    $$domkeytable$$addLeftRight("Super", $$$core$input$keysym$$default.XK_Super_L, $$$core$input$keysym$$default.XK_Super_R);
    // - Symbol
    // - SymbolLock

    // 2.3. Whitespace Keys

    $$domkeytable$$addNumpad("Enter", $$$core$input$keysym$$default.XK_Return, $$$core$input$keysym$$default.XK_KP_Enter);
    $$domkeytable$$addStandard("Tab", $$$core$input$keysym$$default.XK_Tab);
    $$domkeytable$$addNumpad(" ", $$$core$input$keysym$$default.XK_space, $$$core$input$keysym$$default.XK_KP_Space);

    // 2.4. Navigation Keys

    $$domkeytable$$addNumpad("ArrowDown", $$$core$input$keysym$$default.XK_Down, $$$core$input$keysym$$default.XK_KP_Down);
    $$domkeytable$$addNumpad("ArrowUp", $$$core$input$keysym$$default.XK_Up, $$$core$input$keysym$$default.XK_KP_Up);
    $$domkeytable$$addNumpad("ArrowLeft", $$$core$input$keysym$$default.XK_Left, $$$core$input$keysym$$default.XK_KP_Left);
    $$domkeytable$$addNumpad("ArrowRight", $$$core$input$keysym$$default.XK_Right, $$$core$input$keysym$$default.XK_KP_Right);
    $$domkeytable$$addNumpad("End", $$$core$input$keysym$$default.XK_End, $$$core$input$keysym$$default.XK_KP_End);
    $$domkeytable$$addNumpad("Home", $$$core$input$keysym$$default.XK_Home, $$$core$input$keysym$$default.XK_KP_Home);
    $$domkeytable$$addNumpad("PageDown", $$$core$input$keysym$$default.XK_Next, $$$core$input$keysym$$default.XK_KP_Next);
    $$domkeytable$$addNumpad("PageUp", $$$core$input$keysym$$default.XK_Prior, $$$core$input$keysym$$default.XK_KP_Prior);

    // 2.5. Editing Keys

    $$domkeytable$$addStandard("Backspace", $$$core$input$keysym$$default.XK_BackSpace);
    $$domkeytable$$addNumpad("Clear", $$$core$input$keysym$$default.XK_Clear, $$$core$input$keysym$$default.XK_KP_Begin);
    $$domkeytable$$addStandard("Copy", $$$core$input$keysym$$default.XF86XK_Copy);
    // - CrSel
    $$domkeytable$$addStandard("Cut", $$$core$input$keysym$$default.XF86XK_Cut);
    $$domkeytable$$addNumpad("Delete", $$$core$input$keysym$$default.XK_Delete, $$$core$input$keysym$$default.XK_KP_Delete);
    // - EraseEof
    // - ExSel
    $$domkeytable$$addNumpad("Insert", $$$core$input$keysym$$default.XK_Insert, $$$core$input$keysym$$default.XK_KP_Insert);
    $$domkeytable$$addStandard("Paste", $$$core$input$keysym$$default.XF86XK_Paste);
    $$domkeytable$$addStandard("Redo", $$$core$input$keysym$$default.XK_Redo);
    $$domkeytable$$addStandard("Undo", $$$core$input$keysym$$default.XK_Undo);

    // 2.6. UI Keys

    // - Accept
    // - Again (could just be XK_Redo)
    // - Attn
    $$domkeytable$$addStandard("Cancel", $$$core$input$keysym$$default.XK_Cancel);
    $$domkeytable$$addStandard("ContextMenu", $$$core$input$keysym$$default.XK_Menu);
    $$domkeytable$$addStandard("Escape", $$$core$input$keysym$$default.XK_Escape);
    $$domkeytable$$addStandard("Execute", $$$core$input$keysym$$default.XK_Execute);
    $$domkeytable$$addStandard("Find", $$$core$input$keysym$$default.XK_Find);
    $$domkeytable$$addStandard("Help", $$$core$input$keysym$$default.XK_Help);
    $$domkeytable$$addStandard("Pause", $$$core$input$keysym$$default.XK_Pause);
    // - Play
    // - Props
    $$domkeytable$$addStandard("Select", $$$core$input$keysym$$default.XK_Select);
    $$domkeytable$$addStandard("ZoomIn", $$$core$input$keysym$$default.XF86XK_ZoomIn);
    $$domkeytable$$addStandard("ZoomOut", $$$core$input$keysym$$default.XF86XK_ZoomOut);

    // 2.7. Device Keys

    $$domkeytable$$addStandard("BrightnessDown", $$$core$input$keysym$$default.XF86XK_MonBrightnessDown);
    $$domkeytable$$addStandard("BrightnessUp", $$$core$input$keysym$$default.XF86XK_MonBrightnessUp);
    $$domkeytable$$addStandard("Eject", $$$core$input$keysym$$default.XF86XK_Eject);
    $$domkeytable$$addStandard("LogOff", $$$core$input$keysym$$default.XF86XK_LogOff);
    $$domkeytable$$addStandard("Power", $$$core$input$keysym$$default.XF86XK_PowerOff);
    $$domkeytable$$addStandard("PowerOff", $$$core$input$keysym$$default.XF86XK_PowerDown);
    $$domkeytable$$addStandard("PrintScreen", $$$core$input$keysym$$default.XK_Print);
    $$domkeytable$$addStandard("Hibernate", $$$core$input$keysym$$default.XF86XK_Hibernate);
    $$domkeytable$$addStandard("Standby", $$$core$input$keysym$$default.XF86XK_Standby);
    $$domkeytable$$addStandard("WakeUp", $$$core$input$keysym$$default.XF86XK_WakeUp);

    // 2.8. IME and Composition Keys

    $$domkeytable$$addStandard("AllCandidates", $$$core$input$keysym$$default.XK_MultipleCandidate);
    $$domkeytable$$addStandard("Alphanumeric", $$$core$input$keysym$$default.XK_Eisu_Shift); // could also be _Eisu_Toggle
    $$domkeytable$$addStandard("CodeInput", $$$core$input$keysym$$default.XK_Codeinput);
    $$domkeytable$$addStandard("Compose", $$$core$input$keysym$$default.XK_Multi_key);
    $$domkeytable$$addStandard("Convert", $$$core$input$keysym$$default.XK_Henkan);
    // - Dead
    // - FinalMode
    $$domkeytable$$addStandard("GroupFirst", $$$core$input$keysym$$default.XK_ISO_First_Group);
    $$domkeytable$$addStandard("GroupLast", $$$core$input$keysym$$default.XK_ISO_Last_Group);
    $$domkeytable$$addStandard("GroupNext", $$$core$input$keysym$$default.XK_ISO_Next_Group);
    $$domkeytable$$addStandard("GroupPrevious", $$$core$input$keysym$$default.XK_ISO_Prev_Group);
    // - ModeChange (XK_Mode_switch is often used for AltGr)
    // - NextCandidate
    $$domkeytable$$addStandard("NonConvert", $$$core$input$keysym$$default.XK_Muhenkan);
    $$domkeytable$$addStandard("PreviousCandidate", $$$core$input$keysym$$default.XK_PreviousCandidate);
    // - Process
    $$domkeytable$$addStandard("SingleCandidate", $$$core$input$keysym$$default.XK_SingleCandidate);
    $$domkeytable$$addStandard("HangulMode", $$$core$input$keysym$$default.XK_Hangul);
    $$domkeytable$$addStandard("HanjaMode", $$$core$input$keysym$$default.XK_Hangul_Hanja);
    $$domkeytable$$addStandard("JunjuaMode", $$$core$input$keysym$$default.XK_Hangul_Jeonja);
    $$domkeytable$$addStandard("Eisu", $$$core$input$keysym$$default.XK_Eisu_toggle);
    $$domkeytable$$addStandard("Hankaku", $$$core$input$keysym$$default.XK_Hankaku);
    $$domkeytable$$addStandard("Hiragana", $$$core$input$keysym$$default.XK_Hiragana);
    $$domkeytable$$addStandard("HiraganaKatakana", $$$core$input$keysym$$default.XK_Hiragana_Katakana);
    $$domkeytable$$addStandard("KanaMode", $$$core$input$keysym$$default.XK_Kana_Shift); // could also be _Kana_Lock
    $$domkeytable$$addStandard("KanjiMode", $$$core$input$keysym$$default.XK_Kanji);
    $$domkeytable$$addStandard("Katakana", $$$core$input$keysym$$default.XK_Katakana);
    $$domkeytable$$addStandard("Romaji", $$$core$input$keysym$$default.XK_Romaji);
    $$domkeytable$$addStandard("Zenkaku", $$$core$input$keysym$$default.XK_Zenkaku);
    $$domkeytable$$addStandard("ZenkakuHanaku", $$$core$input$keysym$$default.XK_Zenkaku_Hankaku);

    // 2.9. General-Purpose Function Keys

    $$domkeytable$$addStandard("F1", $$$core$input$keysym$$default.XK_F1);
    $$domkeytable$$addStandard("F2", $$$core$input$keysym$$default.XK_F2);
    $$domkeytable$$addStandard("F3", $$$core$input$keysym$$default.XK_F3);
    $$domkeytable$$addStandard("F4", $$$core$input$keysym$$default.XK_F4);
    $$domkeytable$$addStandard("F5", $$$core$input$keysym$$default.XK_F5);
    $$domkeytable$$addStandard("F6", $$$core$input$keysym$$default.XK_F6);
    $$domkeytable$$addStandard("F7", $$$core$input$keysym$$default.XK_F7);
    $$domkeytable$$addStandard("F8", $$$core$input$keysym$$default.XK_F8);
    $$domkeytable$$addStandard("F9", $$$core$input$keysym$$default.XK_F9);
    $$domkeytable$$addStandard("F10", $$$core$input$keysym$$default.XK_F10);
    $$domkeytable$$addStandard("F11", $$$core$input$keysym$$default.XK_F11);
    $$domkeytable$$addStandard("F12", $$$core$input$keysym$$default.XK_F12);
    $$domkeytable$$addStandard("F13", $$$core$input$keysym$$default.XK_F13);
    $$domkeytable$$addStandard("F14", $$$core$input$keysym$$default.XK_F14);
    $$domkeytable$$addStandard("F15", $$$core$input$keysym$$default.XK_F15);
    $$domkeytable$$addStandard("F16", $$$core$input$keysym$$default.XK_F16);
    $$domkeytable$$addStandard("F17", $$$core$input$keysym$$default.XK_F17);
    $$domkeytable$$addStandard("F18", $$$core$input$keysym$$default.XK_F18);
    $$domkeytable$$addStandard("F19", $$$core$input$keysym$$default.XK_F19);
    $$domkeytable$$addStandard("F20", $$$core$input$keysym$$default.XK_F20);
    $$domkeytable$$addStandard("F21", $$$core$input$keysym$$default.XK_F21);
    $$domkeytable$$addStandard("F22", $$$core$input$keysym$$default.XK_F22);
    $$domkeytable$$addStandard("F23", $$$core$input$keysym$$default.XK_F23);
    $$domkeytable$$addStandard("F24", $$$core$input$keysym$$default.XK_F24);
    $$domkeytable$$addStandard("F25", $$$core$input$keysym$$default.XK_F25);
    $$domkeytable$$addStandard("F26", $$$core$input$keysym$$default.XK_F26);
    $$domkeytable$$addStandard("F27", $$$core$input$keysym$$default.XK_F27);
    $$domkeytable$$addStandard("F28", $$$core$input$keysym$$default.XK_F28);
    $$domkeytable$$addStandard("F29", $$$core$input$keysym$$default.XK_F29);
    $$domkeytable$$addStandard("F30", $$$core$input$keysym$$default.XK_F30);
    $$domkeytable$$addStandard("F31", $$$core$input$keysym$$default.XK_F31);
    $$domkeytable$$addStandard("F32", $$$core$input$keysym$$default.XK_F32);
    $$domkeytable$$addStandard("F33", $$$core$input$keysym$$default.XK_F33);
    $$domkeytable$$addStandard("F34", $$$core$input$keysym$$default.XK_F34);
    $$domkeytable$$addStandard("F35", $$$core$input$keysym$$default.XK_F35);
    // - Soft1...

    // 2.10. Multimedia Keys

    // - ChannelDown
    // - ChannelUp
    $$domkeytable$$addStandard("Close", $$$core$input$keysym$$default.XF86XK_Close);
    $$domkeytable$$addStandard("MailForward", $$$core$input$keysym$$default.XF86XK_MailForward);
    $$domkeytable$$addStandard("MailReply", $$$core$input$keysym$$default.XF86XK_Reply);
    $$domkeytable$$addStandard("MainSend", $$$core$input$keysym$$default.XF86XK_Send);
    $$domkeytable$$addStandard("MediaFastForward", $$$core$input$keysym$$default.XF86XK_AudioForward);
    $$domkeytable$$addStandard("MediaPause", $$$core$input$keysym$$default.XF86XK_AudioPause);
    $$domkeytable$$addStandard("MediaPlay", $$$core$input$keysym$$default.XF86XK_AudioPlay);
    $$domkeytable$$addStandard("MediaRecord", $$$core$input$keysym$$default.XF86XK_AudioRecord);
    $$domkeytable$$addStandard("MediaRewind", $$$core$input$keysym$$default.XF86XK_AudioRewind);
    $$domkeytable$$addStandard("MediaStop", $$$core$input$keysym$$default.XF86XK_AudioStop);
    $$domkeytable$$addStandard("MediaTrackNext", $$$core$input$keysym$$default.XF86XK_AudioNext);
    $$domkeytable$$addStandard("MediaTrackPrevious", $$$core$input$keysym$$default.XF86XK_AudioPrev);
    $$domkeytable$$addStandard("New", $$$core$input$keysym$$default.XF86XK_New);
    $$domkeytable$$addStandard("Open", $$$core$input$keysym$$default.XF86XK_Open);
    $$domkeytable$$addStandard("Print", $$$core$input$keysym$$default.XK_Print);
    $$domkeytable$$addStandard("Save", $$$core$input$keysym$$default.XF86XK_Save);
    $$domkeytable$$addStandard("SpellCheck", $$$core$input$keysym$$default.XF86XK_Spell);

    // 2.11. Multimedia Numpad Keys

    // - Key11
    // - Key12

    // 2.12. Audio Keys

    // - AudioBalanceLeft
    // - AudioBalanceRight
    // - AudioBassDown
    // - AudioBassBoostDown
    // - AudioBassBoostToggle
    // - AudioBassBoostUp
    // - AudioBassUp
    // - AudioFaderFront
    // - AudioFaderRear
    // - AudioSurroundModeNext
    // - AudioTrebleDown
    // - AudioTrebleUp
    $$domkeytable$$addStandard("AudioVolumeDown", $$$core$input$keysym$$default.XF86XK_AudioLowerVolume);
    $$domkeytable$$addStandard("AudioVolumeUp", $$$core$input$keysym$$default.XF86XK_AudioRaiseVolume);
    $$domkeytable$$addStandard("AudioVolumeMute", $$$core$input$keysym$$default.XF86XK_AudioMute);
    // - MicrophoneToggle
    // - MicrophoneVolumeDown
    // - MicrophoneVolumeUp
    $$domkeytable$$addStandard("MicrophoneVolumeMute", $$$core$input$keysym$$default.XF86XK_AudioMicMute);

    // 2.13. Speech Keys

    // - SpeechCorrectionList
    // - SpeechInputToggle

    // 2.14. Application Keys

    $$domkeytable$$addStandard("LaunchCalculator", $$$core$input$keysym$$default.XF86XK_Calculator);
    $$domkeytable$$addStandard("LaunchCalendar", $$$core$input$keysym$$default.XF86XK_Calendar);
    $$domkeytable$$addStandard("LaunchMail", $$$core$input$keysym$$default.XF86XK_Mail);
    $$domkeytable$$addStandard("LaunchMediaPlayer", $$$core$input$keysym$$default.XF86XK_AudioMedia);
    $$domkeytable$$addStandard("LaunchMusicPlayer", $$$core$input$keysym$$default.XF86XK_Music);
    $$domkeytable$$addStandard("LaunchMyComputer", $$$core$input$keysym$$default.XF86XK_MyComputer);
    $$domkeytable$$addStandard("LaunchPhone", $$$core$input$keysym$$default.XF86XK_Phone);
    $$domkeytable$$addStandard("LaunchScreenSaver", $$$core$input$keysym$$default.XF86XK_ScreenSaver);
    $$domkeytable$$addStandard("LaunchSpreadsheet", $$$core$input$keysym$$default.XF86XK_Excel);
    $$domkeytable$$addStandard("LaunchWebBrowser", $$$core$input$keysym$$default.XF86XK_WWW);
    $$domkeytable$$addStandard("LaunchWebCam", $$$core$input$keysym$$default.XF86XK_WebCam);
    $$domkeytable$$addStandard("LaunchWordProcessor", $$$core$input$keysym$$default.XF86XK_Word);

    // 2.15. Browser Keys

    $$domkeytable$$addStandard("BrowserBack", $$$core$input$keysym$$default.XF86XK_Back);
    $$domkeytable$$addStandard("BrowserFavorites", $$$core$input$keysym$$default.XF86XK_Favorites);
    $$domkeytable$$addStandard("BrowserForward", $$$core$input$keysym$$default.XF86XK_Forward);
    $$domkeytable$$addStandard("BrowserHome", $$$core$input$keysym$$default.XF86XK_HomePage);
    $$domkeytable$$addStandard("BrowserRefresh", $$$core$input$keysym$$default.XF86XK_Refresh);
    $$domkeytable$$addStandard("BrowserSearch", $$$core$input$keysym$$default.XF86XK_Search);
    $$domkeytable$$addStandard("BrowserStop", $$$core$input$keysym$$default.XF86XK_Stop);

    // 2.16. Mobile Phone Keys

    // - A whole bunch...

    // 2.17. TV Keys

    // - A whole bunch...

    // 2.18. Media Controller Keys

    // - A whole bunch...
    $$domkeytable$$addStandard("Dimmer", $$$core$input$keysym$$default.XF86XK_BrightnessAdjust);
    $$domkeytable$$addStandard("MediaAudioTrack", $$$core$input$keysym$$default.XF86XK_AudioCycleTrack);
    $$domkeytable$$addStandard("RandomToggle", $$$core$input$keysym$$default.XF86XK_AudioRandomPlay);
    $$domkeytable$$addStandard("SplitScreenToggle", $$$core$input$keysym$$default.XF86XK_SplitScreen);
    $$domkeytable$$addStandard("Subtitle", $$$core$input$keysym$$default.XF86XK_Subtitle);
    $$domkeytable$$addStandard("VideoModeNext", $$$core$input$keysym$$default.XF86XK_Next_VMode);

    // Extra: Numpad

    $$domkeytable$$addNumpad("=", $$$core$input$keysym$$default.XK_equal, $$$core$input$keysym$$default.XK_KP_Equal);
    $$domkeytable$$addNumpad("+", $$$core$input$keysym$$default.XK_plus, $$$core$input$keysym$$default.XK_KP_Add);
    $$domkeytable$$addNumpad("-", $$$core$input$keysym$$default.XK_minus, $$$core$input$keysym$$default.XK_KP_Subtract);
    $$domkeytable$$addNumpad("*", $$$core$input$keysym$$default.XK_asterisk, $$$core$input$keysym$$default.XK_KP_Multiply);
    $$domkeytable$$addNumpad("/", $$$core$input$keysym$$default.XK_slash, $$$core$input$keysym$$default.XK_KP_Divide);
    $$domkeytable$$addNumpad(".", $$$core$input$keysym$$default.XK_period, $$$core$input$keysym$$default.XK_KP_Decimal);
    $$domkeytable$$addNumpad(",", $$$core$input$keysym$$default.XK_comma, $$$core$input$keysym$$default.XK_KP_Separator);
    $$domkeytable$$addNumpad("0", $$$core$input$keysym$$default.XK_0, $$$core$input$keysym$$default.XK_KP_0);
    $$domkeytable$$addNumpad("1", $$$core$input$keysym$$default.XK_1, $$$core$input$keysym$$default.XK_KP_1);
    $$domkeytable$$addNumpad("2", $$$core$input$keysym$$default.XK_2, $$$core$input$keysym$$default.XK_KP_2);
    $$domkeytable$$addNumpad("3", $$$core$input$keysym$$default.XK_3, $$$core$input$keysym$$default.XK_KP_3);
    $$domkeytable$$addNumpad("4", $$$core$input$keysym$$default.XK_4, $$$core$input$keysym$$default.XK_KP_4);
    $$domkeytable$$addNumpad("5", $$$core$input$keysym$$default.XK_5, $$$core$input$keysym$$default.XK_KP_5);
    $$domkeytable$$addNumpad("6", $$$core$input$keysym$$default.XK_6, $$$core$input$keysym$$default.XK_KP_6);
    $$domkeytable$$addNumpad("7", $$$core$input$keysym$$default.XK_7, $$$core$input$keysym$$default.XK_KP_7);
    $$domkeytable$$addNumpad("8", $$$core$input$keysym$$default.XK_8, $$$core$input$keysym$$default.XK_KP_8);
    $$domkeytable$$addNumpad("9", $$$core$input$keysym$$default.XK_9, $$$core$input$keysym$$default.XK_KP_9);

    var $$domkeytable$$default = $$domkeytable$$DOMKeyTable;

    function $$util$$getKeycode(evt) {
        // Are we getting proper key identifiers?
        // (unfortunately Firefox and Chrome are crappy here and gives
        // us an empty string on some platforms, rather than leaving it
        // undefined)
        if (evt.code) {
            // Mozilla isn't fully in sync with the spec yet
            switch (evt.code) {
                case 'OSLeft': return 'MetaLeft';
                case 'OSRight': return 'MetaRight';
            }

            return evt.code;
        }

        // The de-facto standard is to use Windows Virtual-Key codes
        // in the 'keyCode' field for non-printable characters. However
        // Webkit sets it to the same as charCode in 'keypress' events.
        if ((evt.type !== 'keypress') && (evt.keyCode in $$vkeys$$default)) {
            let code = $$vkeys$$default[evt.keyCode];

            // macOS has messed up this code for some reason
            if ($$$core$util$browser$$.isMac() && (code === 'ContextMenu')) {
                code = 'MetaRight';
            }

            // The keyCode doesn't distinguish between left and right
            // for the standard modifiers
            if (evt.location === 2) {
                switch (code) {
                    case 'ShiftLeft': return 'ShiftRight';
                    case 'ControlLeft': return 'ControlRight';
                    case 'AltLeft': return 'AltRight';
                }
            }

            // Nor a bunch of the numpad keys
            if (evt.location === 3) {
                switch (code) {
                    case 'Delete': return 'NumpadDecimal';
                    case 'Insert': return 'Numpad0';
                    case 'End': return 'Numpad1';
                    case 'ArrowDown': return 'Numpad2';
                    case 'PageDown': return 'Numpad3';
                    case 'ArrowLeft': return 'Numpad4';
                    case 'ArrowRight': return 'Numpad6';
                    case 'Home': return 'Numpad7';
                    case 'ArrowUp': return 'Numpad8';
                    case 'PageUp': return 'Numpad9';
                    case 'Enter': return 'NumpadEnter';
                }
            }

            return code;
        }

        return 'Unidentified';
    }

    function $$util$$getKey(evt) {
        // Are we getting a proper key value?
        if (evt.key !== undefined) {
            // IE and Edge use some ancient version of the spec
            // https://developer.microsoft.com/en-us/microsoft-edge/platform/issues/8860571/
            switch (evt.key) {
                case 'Spacebar': return ' ';
                case 'Esc': return 'Escape';
                case 'Scroll': return 'ScrollLock';
                case 'Win': return 'Meta';
                case 'Apps': return 'ContextMenu';
                case 'Up': return 'ArrowUp';
                case 'Left': return 'ArrowLeft';
                case 'Right': return 'ArrowRight';
                case 'Down': return 'ArrowDown';
                case 'Del': return 'Delete';
                case 'Divide': return '/';
                case 'Multiply': return '*';
                case 'Subtract': return '-';
                case 'Add': return '+';
                case 'Decimal': return evt.char;
            }

            // Mozilla isn't fully in sync with the spec yet
            switch (evt.key) {
                case 'OS': return 'Meta';
            }

            // iOS leaks some OS names
            switch (evt.key) {
                case 'UIKeyInputUpArrow': return 'ArrowUp';
                case 'UIKeyInputDownArrow': return 'ArrowDown';
                case 'UIKeyInputLeftArrow': return 'ArrowLeft';
                case 'UIKeyInputRightArrow': return 'ArrowRight';
                case 'UIKeyInputEscape': return 'Escape';
            }

            // IE and Edge have broken handling of AltGraph so we cannot
            // trust them for printable characters
            if ((evt.key.length !== 1) || (!$$$core$util$browser$$.isIE() && !$$$core$util$browser$$.isEdge())) {
                return evt.key;
            }
        }

        // Try to deduce it based on the physical key
        const code = $$util$$getKeycode(evt);
        if (code in $$fixedkeys$$default) {
            return $$fixedkeys$$default[code];
        }

        // If that failed, then see if we have a printable character
        if (evt.charCode) {
            return String.fromCharCode(evt.charCode);
        }

        // At this point we have nothing left to go on
        return 'Unidentified';
    }

    function $$util$$getKeysym(evt) {
        const key = $$util$$getKey(evt);

        if (key === 'Unidentified') {
            return null;
        }

        // First look up special keys
        if (key in $$domkeytable$$default) {
            let location = evt.location;

            // Safari screws up location for the right cmd key
            if ((key === 'Meta') && (location === 0)) {
                location = 2;
            }

            if ((location === undefined) || (location > 3)) {
                location = 0;
            }

            return $$domkeytable$$default[key][location];
        }

        // Now we need to look at the Unicode symbol instead

        // Special key? (FIXME: Should have been caught earlier)
        if (key.length !== 1) {
            return null;
        }

        const codepoint = key.charCodeAt();
        if (codepoint) {
            return $$$core$input$keysymdef$$default.lookup(codepoint);
        }

        return null;
    }

    class $$$core$input$keyboard$$Keyboard {
        constructor(target) {
            this._target = target || null;

            this._keyDownList = {};         // List of depressed keys
                                            // (even if they are happy)
            this._pendingKey = null;        // Key waiting for keypress
            this._altGrArmed = false;       // Windows AltGr detection

            // keep these here so we can refer to them later
            this._eventHandlers = {
                'keyup': this._handleKeyUp.bind(this),
                'keydown': this._handleKeyDown.bind(this),
                'keypress': this._handleKeyPress.bind(this),
                'blur': this._allKeysUp.bind(this),
                'checkalt': this._checkAlt.bind(this),
            };

            // ===== EVENT HANDLERS =====

            this.onkeyevent = () => {}; // Handler for key press/release
        }

        // ===== PRIVATE METHODS =====

        _sendKeyEvent(keysym, code, down) {
            if (down) {
                this._keyDownList[code] = keysym;
            } else {
                // Do we really think this key is down?
                if (!(code in this._keyDownList)) {
                    return;
                }
                delete this._keyDownList[code];
            }

            $$$core$util$logging$$.Debug("onkeyevent " + (down ? "down" : "up") +
                      ", keysym: " + keysym, ", code: " + code);
            this.onkeyevent(keysym, code, down);
        }

        _getKeyCode(e) {
            const code = $$util$$.getKeycode(e);
            if (code !== 'Unidentified') {
                return code;
            }

            // Unstable, but we don't have anything else to go on
            // (don't use it for 'keypress' events thought since
            // WebKit sets it to the same as charCode)
            if (e.keyCode && (e.type !== 'keypress')) {
                // 229 is used for composition events
                if (e.keyCode !== 229) {
                    return 'Platform' + e.keyCode;
                }
            }

            // A precursor to the final DOM3 standard. Unfortunately it
            // is not layout independent, so it is as bad as using keyCode
            if (e.keyIdentifier) {
                // Non-character key?
                if (e.keyIdentifier.substr(0, 2) !== 'U+') {
                    return e.keyIdentifier;
                }

                const codepoint = parseInt(e.keyIdentifier.substr(2), 16);
                const char = String.fromCharCode(codepoint).toUpperCase();

                return 'Platform' + char.charCodeAt();
            }

            return 'Unidentified';
        }

        _handleKeyDown(e) {
            const code = this._getKeyCode(e);
            let keysym = $$util$$.getKeysym(e);

            // Windows doesn't have a proper AltGr, but handles it using
            // fake Ctrl+Alt. However the remote end might not be Windows,
            // so we need to merge those in to a single AltGr event. We
            // detect this case by seeing the two key events directly after
            // each other with a very short time between them (<50ms).
            if (this._altGrArmed) {
                this._altGrArmed = false;
                clearTimeout(this._altGrTimeout);

                if ((code === "AltRight") &&
                    ((e.timeStamp - this._altGrCtrlTime) < 50)) {
                    // FIXME: We fail to detect this if either Ctrl key is
                    //        first manually pressed as Windows then no
                    //        longer sends the fake Ctrl down event. It
                    //        does however happily send real Ctrl events
                    //        even when AltGr is already down. Some
                    //        browsers detect this for us though and set the
                    //        key to "AltGraph".
                    keysym = $$$core$input$keysym$$default.XK_ISO_Level3_Shift;
                } else {
                    this._sendKeyEvent($$$core$input$keysym$$default.XK_Control_L, "ControlLeft", true);
                }
            }

            // We cannot handle keys we cannot track, but we also need
            // to deal with virtual keyboards which omit key info
            // (iOS omits tracking info on keyup events, which forces us to
            // special treat that platform here)
            if ((code === 'Unidentified') || $$$core$util$browser$$.isIOS()) {
                if (keysym) {
                    // If it's a virtual keyboard then it should be
                    // sufficient to just send press and release right
                    // after each other
                    this._sendKeyEvent(keysym, code, true);
                    this._sendKeyEvent(keysym, code, false);
                }

                $$$core$util$events$$stopEvent(e);
                return;
            }

            // Alt behaves more like AltGraph on macOS, so shuffle the
            // keys around a bit to make things more sane for the remote
            // server. This method is used by RealVNC and TigerVNC (and
            // possibly others).
            if ($$$core$util$browser$$.isMac()) {
                switch (keysym) {
                    case $$$core$input$keysym$$default.XK_Super_L:
                        keysym = $$$core$input$keysym$$default.XK_Alt_L;
                        break;
                    case $$$core$input$keysym$$default.XK_Super_R:
                        keysym = $$$core$input$keysym$$default.XK_Super_L;
                        break;
                    case $$$core$input$keysym$$default.XK_Alt_L:
                        keysym = $$$core$input$keysym$$default.XK_Mode_switch;
                        break;
                    case $$$core$input$keysym$$default.XK_Alt_R:
                        keysym = $$$core$input$keysym$$default.XK_ISO_Level3_Shift;
                        break;
                }
            }

            // Is this key already pressed? If so, then we must use the
            // same keysym or we'll confuse the server
            if (code in this._keyDownList) {
                keysym = this._keyDownList[code];
            }

            // macOS doesn't send proper key events for modifiers, only
            // state change events. That gets extra confusing for CapsLock
            // which toggles on each press, but not on release. So pretend
            // it was a quick press and release of the button.
            if ($$$core$util$browser$$.isMac() && (code === 'CapsLock')) {
                this._sendKeyEvent($$$core$input$keysym$$default.XK_Caps_Lock, 'CapsLock', true);
                this._sendKeyEvent($$$core$input$keysym$$default.XK_Caps_Lock, 'CapsLock', false);
                $$$core$util$events$$stopEvent(e);
                return;
            }

            // If this is a legacy browser then we'll need to wait for
            // a keypress event as well
            // (IE and Edge has a broken KeyboardEvent.key, so we can't
            // just check for the presence of that field)
            if (!keysym && (!e.key || $$$core$util$browser$$.isIE() || $$$core$util$browser$$.isEdge())) {
                this._pendingKey = code;
                // However we might not get a keypress event if the key
                // is non-printable, which needs some special fallback
                // handling
                setTimeout(this._handleKeyPressTimeout.bind(this), 10, e);
                return;
            }

            this._pendingKey = null;
            $$$core$util$events$$stopEvent(e);

            // Possible start of AltGr sequence? (see above)
            if ((code === "ControlLeft") && $$$core$util$browser$$.isWindows() &&
                !("ControlLeft" in this._keyDownList)) {
                this._altGrArmed = true;
                this._altGrTimeout = setTimeout(this._handleAltGrTimeout.bind(this), 100);
                this._altGrCtrlTime = e.timeStamp;
                return;
            }

            this._sendKeyEvent(keysym, code, true);
        }

        // Legacy event for browsers without code/key
        _handleKeyPress(e) {
            $$$core$util$events$$stopEvent(e);

            // Are we expecting a keypress?
            if (this._pendingKey === null) {
                return;
            }

            let code = this._getKeyCode(e);
            const keysym = $$util$$.getKeysym(e);

            // The key we were waiting for?
            if ((code !== 'Unidentified') && (code != this._pendingKey)) {
                return;
            }

            code = this._pendingKey;
            this._pendingKey = null;

            if (!keysym) {
                $$$core$util$logging$$.Info('keypress with no keysym:', e);
                return;
            }

            this._sendKeyEvent(keysym, code, true);
        }

        _handleKeyPressTimeout(e) {
            // Did someone manage to sort out the key already?
            if (this._pendingKey === null) {
                return;
            }

            let keysym;

            const code = this._pendingKey;
            this._pendingKey = null;

            // We have no way of knowing the proper keysym with the
            // information given, but the following are true for most
            // layouts
            if ((e.keyCode >= 0x30) && (e.keyCode <= 0x39)) {
                // Digit
                keysym = e.keyCode;
            } else if ((e.keyCode >= 0x41) && (e.keyCode <= 0x5a)) {
                // Character (A-Z)
                let char = String.fromCharCode(e.keyCode);
                // A feeble attempt at the correct case
                if (e.shiftKey) {
                    char = char.toUpperCase();
                } else {
                    char = char.toLowerCase();
                }
                keysym = char.charCodeAt();
            } else {
                // Unknown, give up
                keysym = 0;
            }

            this._sendKeyEvent(keysym, code, true);
        }

        _handleKeyUp(e) {
            $$$core$util$events$$stopEvent(e);

            const code = this._getKeyCode(e);

            // We can't get a release in the middle of an AltGr sequence, so
            // abort that detection
            if (this._altGrArmed) {
                this._altGrArmed = false;
                clearTimeout(this._altGrTimeout);
                this._sendKeyEvent($$$core$input$keysym$$default.XK_Control_L, "ControlLeft", true);
            }

            // See comment in _handleKeyDown()
            if ($$$core$util$browser$$.isMac() && (code === 'CapsLock')) {
                this._sendKeyEvent($$$core$input$keysym$$default.XK_Caps_Lock, 'CapsLock', true);
                this._sendKeyEvent($$$core$input$keysym$$default.XK_Caps_Lock, 'CapsLock', false);
                return;
            }

            this._sendKeyEvent(this._keyDownList[code], code, false);
        }

        _handleAltGrTimeout() {
            this._altGrArmed = false;
            clearTimeout(this._altGrTimeout);
            this._sendKeyEvent($$$core$input$keysym$$default.XK_Control_L, "ControlLeft", true);
        }

        _allKeysUp() {
            $$$core$util$logging$$.Debug(">> Keyboard.allKeysUp");
            for (let code in this._keyDownList) {
                this._sendKeyEvent(this._keyDownList[code], code, false);
            }
            $$$core$util$logging$$.Debug("<< Keyboard.allKeysUp");
        }

        // Firefox Alt workaround, see below
        _checkAlt(e) {
            if (e.altKey) {
                return;
            }

            const target = this._target;
            const downList = this._keyDownList;
            ['AltLeft', 'AltRight'].forEach((code) => {
                if (!(code in downList)) {
                    return;
                }

                const event = new KeyboardEvent('keyup',
                                                { key: downList[code],
                                                  code: code });
                target.dispatchEvent(event);
            });
        }

        // ===== PUBLIC METHODS =====

        grab() {
            //Log.Debug(">> Keyboard.grab");

            this._target.addEventListener('keydown', this._eventHandlers.keydown);
            this._target.addEventListener('keyup', this._eventHandlers.keyup);
            this._target.addEventListener('keypress', this._eventHandlers.keypress);

            // Release (key up) if window loses focus
            window.addEventListener('blur', this._eventHandlers.blur);

            // Firefox has broken handling of Alt, so we need to poll as
            // best we can for releases (still doesn't prevent the menu
            // from popping up though as we can't call preventDefault())
            if ($$$core$util$browser$$.isWindows() && $$$core$util$browser$$.isFirefox()) {
                const handler = this._eventHandlers.checkalt;
                ['mousedown', 'mouseup', 'mousemove', 'wheel',
                 'touchstart', 'touchend', 'touchmove',
                 'keydown', 'keyup'].forEach(type =>
                    document.addEventListener(type, handler,
                                              { capture: true,
                                                passive: true }));
            }

            //Log.Debug("<< Keyboard.grab");
        }

        ungrab() {
            //Log.Debug(">> Keyboard.ungrab");

            if ($$$core$util$browser$$.isWindows() && $$$core$util$browser$$.isFirefox()) {
                const handler = this._eventHandlers.checkalt;
                ['mousedown', 'mouseup', 'mousemove', 'wheel',
                 'touchstart', 'touchend', 'touchmove',
                 'keydown', 'keyup'].forEach(type => document.removeEventListener(type, handler));
            }

            this._target.removeEventListener('keydown', this._eventHandlers.keydown);
            this._target.removeEventListener('keyup', this._eventHandlers.keyup);
            this._target.removeEventListener('keypress', this._eventHandlers.keypress);
            window.removeEventListener('blur', this._eventHandlers.blur);

            // Release (key up) all keys that are in a down state
            this._allKeysUp();

            //Log.Debug(">> Keyboard.ungrab");
        }
    }

    var $$$core$input$keyboard$$default = $$$core$input$keyboard$$Keyboard;

    function $$util$strings$$decodeUTF8(utf8string) {
        return decodeURIComponent(escape(utf8string));
    }

    class $$util$eventtarget$$EventTargetMixin {
        constructor() {
            this._listeners = new Map();
        }

        addEventListener(type, callback) {
            if (!this._listeners.has(type)) {
                this._listeners.set(type, new Set());
            }
            this._listeners.get(type).add(callback);
        }

        removeEventListener(type, callback) {
            if (this._listeners.has(type)) {
                this._listeners.get(type).delete(callback);
            }
        }

        dispatchEvent(event) {
            if (!this._listeners.has(event.type)) {
                return true;
            }
            this._listeners.get(event.type)
                .forEach(callback => callback.call(this, event));
            return !event.defaultPrevented;
        }
    }

    var $$util$eventtarget$$default = $$util$eventtarget$$EventTargetMixin;

    var $$base64$$default = {
        /* Convert data (an array of integers) to a Base64 string. */
        toBase64Table: 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/='.split(''),

        base64Pad: '=',

        encode(data) {
            "use strict";
            let result = '';
            const length = data.length;
            const lengthpad = (length % 3);
            // Convert every three bytes to 4 ascii characters.

            for (let i = 0; i < (length - 2); i += 3) {
                result += this.toBase64Table[data[i] >> 2];
                result += this.toBase64Table[((data[i] & 0x03) << 4) + (data[i + 1] >> 4)];
                result += this.toBase64Table[((data[i + 1] & 0x0f) << 2) + (data[i + 2] >> 6)];
                result += this.toBase64Table[data[i + 2] & 0x3f];
            }

            // Convert the remaining 1 or 2 bytes, pad out to 4 characters.
            const j = length - lengthpad;
            if (lengthpad === 2) {
                result += this.toBase64Table[data[j] >> 2];
                result += this.toBase64Table[((data[j] & 0x03) << 4) + (data[j + 1] >> 4)];
                result += this.toBase64Table[(data[j + 1] & 0x0f) << 2];
                result += this.toBase64Table[64];
            } else if (lengthpad === 1) {
                result += this.toBase64Table[data[j] >> 2];
                result += this.toBase64Table[(data[j] & 0x03) << 4];
                result += this.toBase64Table[64];
                result += this.toBase64Table[64];
            }

            return result;
        },

        /* Convert Base64 data to a string */
        /* eslint-disable comma-spacing */
        toBinaryTable: [
            -1,-1,-1,-1, -1,-1,-1,-1, -1,-1,-1,-1, -1,-1,-1,-1,
            -1,-1,-1,-1, -1,-1,-1,-1, -1,-1,-1,-1, -1,-1,-1,-1,
            -1,-1,-1,-1, -1,-1,-1,-1, -1,-1,-1,62, -1,-1,-1,63,
            52,53,54,55, 56,57,58,59, 60,61,-1,-1, -1, 0,-1,-1,
            -1, 0, 1, 2,  3, 4, 5, 6,  7, 8, 9,10, 11,12,13,14,
            15,16,17,18, 19,20,21,22, 23,24,25,-1, -1,-1,-1,-1,
            -1,26,27,28, 29,30,31,32, 33,34,35,36, 37,38,39,40,
            41,42,43,44, 45,46,47,48, 49,50,51,-1, -1,-1,-1,-1
        ],

        /* eslint-enable comma-spacing */

        decode(data, offset = 0) {
            let data_length = data.indexOf('=') - offset;
            if (data_length < 0) { data_length = data.length - offset; }

            /* Every four characters is 3 resulting numbers */
            const result_length = (data_length >> 2) * 3 + Math.floor((data_length % 4) / 1.5);
            const result = new Array(result_length);

            // Convert one by one.

            let leftbits = 0; // number of bits decoded, but yet to be appended
            let leftdata = 0; // bits decoded, but yet to be appended
            for (let idx = 0, i = offset; i < data.length; i++) {
                const c = this.toBinaryTable[data.charCodeAt(i) & 0x7f];
                const padding = (data.charAt(i) === this.base64Pad);
                // Skip illegal characters and whitespace
                if (c === -1) {
                    $$$core$util$logging$$.Error("Illegal character code " + data.charCodeAt(i) + " at position " + i);
                    continue;
                }

                // Collect data into leftdata, update bitcount
                leftdata = (leftdata << 6) | c;
                leftbits += 6;

                // If we have 8 or more bits, append 8 bits to the result
                if (leftbits >= 8) {
                    leftbits -= 8;
                    // Append if not padding.
                    if (!padding) {
                        result[idx++] = (leftdata >> leftbits) & 0xff;
                    }
                    leftdata &= (1 << leftbits) - 1;
                }
            }

            // If there are any bits left, the base64 string was corrupted
            if (leftbits) {
                const err = new Error('Corrupted base64 string');
                err.name = 'Base64-Error';
                throw err;
            }

            return result;
        }
    };

    class $$display$$Display {
        constructor(target) {
            this._drawCtx = null;
            this._c_forceCanvas = false;

            this._renderQ = [];  // queue drawing actions for in-oder rendering
            this._flushing = false;

            // the full frame buffer (logical canvas) size
            this._fb_width = 0;
            this._fb_height = 0;

            this._prevDrawStyle = "";
            this._tile = null;
            this._tile16x16 = null;
            this._tile_x = 0;
            this._tile_y = 0;

            $$$core$util$logging$$.Debug(">> Display.constructor");

            // The visible canvas
            this._target = target;

            if (!this._target) {
                throw new Error("Target must be set");
            }

            if (typeof this._target === 'string') {
                throw new Error('target must be a DOM element');
            }

            if (!this._target.getContext) {
                throw new Error("no getContext method");
            }

            this._targetCtx = this._target.getContext('2d');

            // the visible canvas viewport (i.e. what actually gets seen)
            this._viewportLoc = { 'x': 0, 'y': 0, 'w': this._target.width, 'h': this._target.height };

            // The hidden canvas, where we do the actual rendering
            this._backbuffer = document.createElement('canvas');
            this._drawCtx = this._backbuffer.getContext('2d');

            this._damageBounds = { left: 0, top: 0,
                                   right: this._backbuffer.width,
                                   bottom: this._backbuffer.height };

            $$$core$util$logging$$.Debug("User Agent: " + navigator.userAgent);

            this.clear();

            // Check canvas features
            if (!('createImageData' in this._drawCtx)) {
                throw new Error("Canvas does not support createImageData");
            }

            this._tile16x16 = this._drawCtx.createImageData(16, 16);
            $$$core$util$logging$$.Debug("<< Display.constructor");

            // ===== PROPERTIES =====

            this._scale = 1.0;
            this._clipViewport = false;
            this.logo = null;

            // ===== EVENT HANDLERS =====

            this.onflush = () => {}; // A flush request has finished
        }

        // ===== PROPERTIES =====

        get scale() { return this._scale; }
        set scale(scale) {
            this._rescale(scale);
        }

        get clipViewport() { return this._clipViewport; }
        set clipViewport(viewport) {
            this._clipViewport = viewport;
            // May need to readjust the viewport dimensions
            const vp = this._viewportLoc;
            this.viewportChangeSize(vp.w, vp.h);
            this.viewportChangePos(0, 0);
        }

        get width() {
            return this._fb_width;
        }

        get height() {
            return this._fb_height;
        }

        // ===== PUBLIC METHODS =====

        viewportChangePos(deltaX, deltaY) {
            const vp = this._viewportLoc;
            deltaX = Math.floor(deltaX);
            deltaY = Math.floor(deltaY);

            if (!this._clipViewport) {
                deltaX = -vp.w;  // clamped later of out of bounds
                deltaY = -vp.h;
            }

            const vx2 = vp.x + vp.w - 1;
            const vy2 = vp.y + vp.h - 1;

            // Position change

            if (deltaX < 0 && vp.x + deltaX < 0) {
                deltaX = -vp.x;
            }
            if (vx2 + deltaX >= this._fb_width) {
                deltaX -= vx2 + deltaX - this._fb_width + 1;
            }

            if (vp.y + deltaY < 0) {
                deltaY = -vp.y;
            }
            if (vy2 + deltaY >= this._fb_height) {
                deltaY -= (vy2 + deltaY - this._fb_height + 1);
            }

            if (deltaX === 0 && deltaY === 0) {
                return;
            }
            $$$core$util$logging$$.Debug("viewportChange deltaX: " + deltaX + ", deltaY: " + deltaY);

            vp.x += deltaX;
            vp.y += deltaY;

            this._damage(vp.x, vp.y, vp.w, vp.h);

            this.flip();
        }

        viewportChangeSize(width, height) {

            if (!this._clipViewport ||
                typeof(width) === "undefined" ||
                typeof(height) === "undefined") {

                $$$core$util$logging$$.Debug("Setting viewport to full display region");
                width = this._fb_width;
                height = this._fb_height;
            }

            width = Math.floor(width);
            height = Math.floor(height);

            if (width > this._fb_width) {
                width = this._fb_width;
            }
            if (height > this._fb_height) {
                height = this._fb_height;
            }

            const vp = this._viewportLoc;
            if (vp.w !== width || vp.h !== height) {
                vp.w = width;
                vp.h = height;

                const canvas = this._target;
                canvas.width = width;
                canvas.height = height;

                // The position might need to be updated if we've grown
                this.viewportChangePos(0, 0);

                this._damage(vp.x, vp.y, vp.w, vp.h);
                this.flip();

                // Update the visible size of the target canvas
                this._rescale(this._scale);
            }
        }

        absX(x) {
            if (this._scale === 0) {
                return 0;
            }
            return x / this._scale + this._viewportLoc.x;
        }

        absY(y) {
            if (this._scale === 0) {
                return 0;
            }
            return y / this._scale + this._viewportLoc.y;
        }

        resize(width, height) {
            this._prevDrawStyle = "";

            this._fb_width = width;
            this._fb_height = height;

            const canvas = this._backbuffer;
            if (canvas.width !== width || canvas.height !== height) {

                // We have to save the canvas data since changing the size will clear it
                let saveImg = null;
                if (canvas.width > 0 && canvas.height > 0) {
                    saveImg = this._drawCtx.getImageData(0, 0, canvas.width, canvas.height);
                }

                if (canvas.width !== width) {
                    canvas.width = width;
                }
                if (canvas.height !== height) {
                    canvas.height = height;
                }

                if (saveImg) {
                    this._drawCtx.putImageData(saveImg, 0, 0);
                }
            }

            // Readjust the viewport as it may be incorrectly sized
            // and positioned
            const vp = this._viewportLoc;
            this.viewportChangeSize(vp.w, vp.h);
            this.viewportChangePos(0, 0);
        }

        // Track what parts of the visible canvas that need updating
        _damage(x, y, w, h) {
            if (x < this._damageBounds.left) {
                this._damageBounds.left = x;
            }
            if (y < this._damageBounds.top) {
                this._damageBounds.top = y;
            }
            if ((x + w) > this._damageBounds.right) {
                this._damageBounds.right = x + w;
            }
            if ((y + h) > this._damageBounds.bottom) {
                this._damageBounds.bottom = y + h;
            }
        }

        // Update the visible canvas with the contents of the
        // rendering canvas
        flip(from_queue) {
            if (this._renderQ.length !== 0 && !from_queue) {
                this._renderQ_push({
                    'type': 'flip'
                });
            } else {
                let x = this._damageBounds.left;
                let y = this._damageBounds.top;
                let w = this._damageBounds.right - x;
                let h = this._damageBounds.bottom - y;

                let vx = x - this._viewportLoc.x;
                let vy = y - this._viewportLoc.y;

                if (vx < 0) {
                    w += vx;
                    x -= vx;
                    vx = 0;
                }
                if (vy < 0) {
                    h += vy;
                    y -= vy;
                    vy = 0;
                }

                if ((vx + w) > this._viewportLoc.w) {
                    w = this._viewportLoc.w - vx;
                }
                if ((vy + h) > this._viewportLoc.h) {
                    h = this._viewportLoc.h - vy;
                }

                if ((w > 0) && (h > 0)) {
                    // FIXME: We may need to disable image smoothing here
                    //        as well (see copyImage()), but we haven't
                    //        noticed any problem yet.
                    this._targetCtx.drawImage(this._backbuffer,
                                              x, y, w, h,
                                              vx, vy, w, h);
                }

                this._damageBounds.left = this._damageBounds.top = 65535;
                this._damageBounds.right = this._damageBounds.bottom = 0;
            }
        }

        clear() {
            if (this._logo) {
                this.resize(this._logo.width, this._logo.height);
                this.imageRect(0, 0, this._logo.type, this._logo.data);
            } else {
                this.resize(240, 20);
                this._drawCtx.clearRect(0, 0, this._fb_width, this._fb_height);
            }
            this.flip();
        }

        pending() {
            return this._renderQ.length > 0;
        }

        flush() {
            if (this._renderQ.length === 0) {
                this.onflush();
            } else {
                this._flushing = true;
            }
        }

        fillRect(x, y, width, height, color, from_queue) {
            if (this._renderQ.length !== 0 && !from_queue) {
                this._renderQ_push({
                    'type': 'fill',
                    'x': x,
                    'y': y,
                    'width': width,
                    'height': height,
                    'color': color
                });
            } else {
                this._setFillColor(color);
                this._drawCtx.fillRect(x, y, width, height);
                this._damage(x, y, width, height);
            }
        }

        copyImage(old_x, old_y, new_x, new_y, w, h, from_queue) {
            if (this._renderQ.length !== 0 && !from_queue) {
                this._renderQ_push({
                    'type': 'copy',
                    'old_x': old_x,
                    'old_y': old_y,
                    'x': new_x,
                    'y': new_y,
                    'width': w,
                    'height': h,
                });
            } else {
                // Due to this bug among others [1] we need to disable the image-smoothing to
                // avoid getting a blur effect when copying data.
                //
                // 1. https://bugzilla.mozilla.org/show_bug.cgi?id=1194719
                //
                // We need to set these every time since all properties are reset
                // when the the size is changed
                this._drawCtx.mozImageSmoothingEnabled = false;
                this._drawCtx.webkitImageSmoothingEnabled = false;
                this._drawCtx.msImageSmoothingEnabled = false;
                this._drawCtx.imageSmoothingEnabled = false;

                this._drawCtx.drawImage(this._backbuffer,
                                        old_x, old_y, w, h,
                                        new_x, new_y, w, h);
                this._damage(new_x, new_y, w, h);
            }
        }

        imageRect(x, y, mime, arr) {
            const img = new Image();
            img.src = "data: " + mime + ";base64," + $$base64$$default.encode(arr);
            this._renderQ_push({
                'type': 'img',
                'img': img,
                'x': x,
                'y': y
            });
        }

        // start updating a tile
        startTile(x, y, width, height, color) {
            this._tile_x = x;
            this._tile_y = y;
            if (width === 16 && height === 16) {
                this._tile = this._tile16x16;
            } else {
                this._tile = this._drawCtx.createImageData(width, height);
            }

            const red = color[2];
            const green = color[1];
            const blue = color[0];

            const data = this._tile.data;
            for (let i = 0; i < width * height * 4; i += 4) {
                data[i] = red;
                data[i + 1] = green;
                data[i + 2] = blue;
                data[i + 3] = 255;
            }
        }

        // update sub-rectangle of the current tile
        subTile(x, y, w, h, color) {
            const red = color[2];
            const green = color[1];
            const blue = color[0];
            const xend = x + w;
            const yend = y + h;

            const data = this._tile.data;
            const width = this._tile.width;
            for (let j = y; j < yend; j++) {
                for (let i = x; i < xend; i++) {
                    const p = (i + (j * width)) * 4;
                    data[p] = red;
                    data[p + 1] = green;
                    data[p + 2] = blue;
                    data[p + 3] = 255;
                }
            }
        }

        // draw the current tile to the screen
        finishTile() {
            this._drawCtx.putImageData(this._tile, this._tile_x, this._tile_y);
            this._damage(this._tile_x, this._tile_y,
                         this._tile.width, this._tile.height);
        }

        blitImage(x, y, width, height, arr, offset, from_queue) {
            if (this._renderQ.length !== 0 && !from_queue) {
                // NB(directxman12): it's technically more performant here to use preallocated arrays,
                // but it's a lot of extra work for not a lot of payoff -- if we're using the render queue,
                // this probably isn't getting called *nearly* as much
                const new_arr = new Uint8Array(width * height * 4);
                new_arr.set(new Uint8Array(arr.buffer, 0, new_arr.length));
                this._renderQ_push({
                    'type': 'blit',
                    'data': new_arr,
                    'x': x,
                    'y': y,
                    'width': width,
                    'height': height,
                });
            } else {
                this._bgrxImageData(x, y, width, height, arr, offset);
            }
        }

        blitRgbImage(x, y, width, height, arr, offset, from_queue) {
            if (this._renderQ.length !== 0 && !from_queue) {
                // NB(directxman12): it's technically more performant here to use preallocated arrays,
                // but it's a lot of extra work for not a lot of payoff -- if we're using the render queue,
                // this probably isn't getting called *nearly* as much
                const new_arr = new Uint8Array(width * height * 3);
                new_arr.set(new Uint8Array(arr.buffer, 0, new_arr.length));
                this._renderQ_push({
                    'type': 'blitRgb',
                    'data': new_arr,
                    'x': x,
                    'y': y,
                    'width': width,
                    'height': height,
                });
            } else {
                this._rgbImageData(x, y, width, height, arr, offset);
            }
        }

        blitRgbxImage(x, y, width, height, arr, offset, from_queue) {
            if (this._renderQ.length !== 0 && !from_queue) {
                // NB(directxman12): it's technically more performant here to use preallocated arrays,
                // but it's a lot of extra work for not a lot of payoff -- if we're using the render queue,
                // this probably isn't getting called *nearly* as much
                const new_arr = new Uint8Array(width * height * 4);
                new_arr.set(new Uint8Array(arr.buffer, 0, new_arr.length));
                this._renderQ_push({
                    'type': 'blitRgbx',
                    'data': new_arr,
                    'x': x,
                    'y': y,
                    'width': width,
                    'height': height,
                });
            } else {
                this._rgbxImageData(x, y, width, height, arr, offset);
            }
        }

        drawImage(img, x, y) {
            this._drawCtx.drawImage(img, x, y);
            this._damage(x, y, img.width, img.height);
        }

        autoscale(containerWidth, containerHeight) {
            let scaleRatio;

            if (containerWidth === 0 || containerHeight === 0) {
                scaleRatio = 0;

            } else {

                const vp = this._viewportLoc;
                const targetAspectRatio = containerWidth / containerHeight;
                const fbAspectRatio = vp.w / vp.h;

                if (fbAspectRatio >= targetAspectRatio) {
                    scaleRatio = containerWidth / vp.w;
                } else {
                    scaleRatio = containerHeight / vp.h;
                }
            }

            this._rescale(scaleRatio);
        }

        // ===== PRIVATE METHODS =====

        _rescale(factor) {
            this._scale = factor;
            const vp = this._viewportLoc;

            // NB(directxman12): If you set the width directly, or set the
            //                   style width to a number, the canvas is cleared.
            //                   However, if you set the style width to a string
            //                   ('NNNpx'), the canvas is scaled without clearing.
            const width = factor * vp.w + 'px';
            const height = factor * vp.h + 'px';

            if ((this._target.style.width !== width) ||
                (this._target.style.height !== height)) {
                this._target.style.width = width;
                this._target.style.height = height;
            }
        }

        _setFillColor(color) {
            const newStyle = 'rgb(' + color[2] + ',' + color[1] + ',' + color[0] + ')';
            if (newStyle !== this._prevDrawStyle) {
                this._drawCtx.fillStyle = newStyle;
                this._prevDrawStyle = newStyle;
            }
        }

        _rgbImageData(x, y, width, height, arr, offset) {
            const img = this._drawCtx.createImageData(width, height);
            const data = img.data;
            for (let i = 0, j = offset; i < width * height * 4; i += 4, j += 3) {
                data[i]     = arr[j];
                data[i + 1] = arr[j + 1];
                data[i + 2] = arr[j + 2];
                data[i + 3] = 255;  // Alpha
            }
            this._drawCtx.putImageData(img, x, y);
            this._damage(x, y, img.width, img.height);
        }

        _bgrxImageData(x, y, width, height, arr, offset) {
            const img = this._drawCtx.createImageData(width, height);
            const data = img.data;
            for (let i = 0, j = offset; i < width * height * 4; i += 4, j += 4) {
                data[i]     = arr[j + 2];
                data[i + 1] = arr[j + 1];
                data[i + 2] = arr[j];
                data[i + 3] = 255;  // Alpha
            }
            this._drawCtx.putImageData(img, x, y);
            this._damage(x, y, img.width, img.height);
        }

        _rgbxImageData(x, y, width, height, arr, offset) {
            // NB(directxman12): arr must be an Type Array view
            let img;
            if ($$$core$util$browser$$supportsImageMetadata) {
                img = new ImageData(new Uint8ClampedArray(arr.buffer, arr.byteOffset, width * height * 4), width, height);
            } else {
                img = this._drawCtx.createImageData(width, height);
                img.data.set(new Uint8ClampedArray(arr.buffer, arr.byteOffset, width * height * 4));
            }
            this._drawCtx.putImageData(img, x, y);
            this._damage(x, y, img.width, img.height);
        }

        _renderQ_push(action) {
            this._renderQ.push(action);
            if (this._renderQ.length === 1) {
                // If this can be rendered immediately it will be, otherwise
                // the scanner will wait for the relevant event
                this._scan_renderQ();
            }
        }

        _resume_renderQ() {
            // "this" is the object that is ready, not the
            // display object
            this.removeEventListener('load', this._noVNC_display._resume_renderQ);
            this._noVNC_display._scan_renderQ();
        }

        _scan_renderQ() {
            let ready = true;
            while (ready && this._renderQ.length > 0) {
                const a = this._renderQ[0];
                switch (a.type) {
                    case 'flip':
                        this.flip(true);
                        break;
                    case 'copy':
                        this.copyImage(a.old_x, a.old_y, a.x, a.y, a.width, a.height, true);
                        break;
                    case 'fill':
                        this.fillRect(a.x, a.y, a.width, a.height, a.color, true);
                        break;
                    case 'blit':
                        this.blitImage(a.x, a.y, a.width, a.height, a.data, 0, true);
                        break;
                    case 'blitRgb':
                        this.blitRgbImage(a.x, a.y, a.width, a.height, a.data, 0, true);
                        break;
                    case 'blitRgbx':
                        this.blitRgbxImage(a.x, a.y, a.width, a.height, a.data, 0, true);
                        break;
                    case 'img':
                        if (a.img.complete) {
                            this.drawImage(a.img, a.x, a.y);
                        } else {
                            a.img._noVNC_display = this;
                            a.img.addEventListener('load', this._resume_renderQ);
                            // We need to wait for this image to 'load'
                            // to keep things in-order
                            ready = false;
                        }
                        break;
                }

                if (ready) {
                    this._renderQ.shift();
                }
            }

            if (this._renderQ.length === 0 && this._flushing) {
                this._flushing = false;
                this.onflush();
            }
        }
    }

    var $$display$$default = $$display$$Display;

    const $$input$mouse$$WHEEL_STEP = 10; // Delta threshold for a mouse wheel step
    const $$input$mouse$$WHEEL_STEP_TIMEOUT = 50; // ms
    const $$input$mouse$$WHEEL_LINE_HEIGHT = 19;

    class $$input$mouse$$Mouse {
        constructor(target) {
            this._target = target || document;

            this._doubleClickTimer = null;
            this._lastTouchPos = null;

            this._pos = null;
            this._wheelStepXTimer = null;
            this._wheelStepYTimer = null;
            this._accumulatedWheelDeltaX = 0;
            this._accumulatedWheelDeltaY = 0;

            this._eventHandlers = {
                'mousedown': this._handleMouseDown.bind(this),
                'mouseup': this._handleMouseUp.bind(this),
                'mousemove': this._handleMouseMove.bind(this),
                'mousewheel': this._handleMouseWheel.bind(this),
                'mousedisable': this._handleMouseDisable.bind(this)
            };

            // ===== PROPERTIES =====

            this.touchButton = 1;                 // Button mask (1, 2, 4) for touch devices (0 means ignore clicks)

            // ===== EVENT HANDLERS =====

            this.onmousebutton = () => {}; // Handler for mouse button click/release
            this.onmousemove = () => {}; // Handler for mouse movement
        }

        // ===== PRIVATE METHODS =====

        _resetDoubleClickTimer() {
            this._doubleClickTimer = null;
        }

        _handleMouseButton(e, down) {
            this._updateMousePosition(e);
            let pos = this._pos;

            let bmask;
            if (e.touches || e.changedTouches) {
                // Touch device

                // When two touches occur within 500 ms of each other and are
                // close enough together a double click is triggered.
                if (down == 1) {
                    if (this._doubleClickTimer === null) {
                        this._lastTouchPos = pos;
                    } else {
                        clearTimeout(this._doubleClickTimer);

                        // When the distance between the two touches is small enough
                        // force the position of the latter touch to the position of
                        // the first.

                        const xs = this._lastTouchPos.x - pos.x;
                        const ys = this._lastTouchPos.y - pos.y;
                        const d = Math.sqrt((xs * xs) + (ys * ys));

                        // The goal is to trigger on a certain physical width, the
                        // devicePixelRatio brings us a bit closer but is not optimal.
                        const threshold = 20 * (window.devicePixelRatio || 1);
                        if (d < threshold) {
                            pos = this._lastTouchPos;
                        }
                    }
                    this._doubleClickTimer = setTimeout(this._resetDoubleClickTimer.bind(this), 500);
                }
                bmask = this.touchButton;
                // If bmask is set
            } else if (e.which) {
                /* everything except IE */
                bmask = 1 << e.button;
            } else {
                /* IE including 9 */
                bmask = (e.button & 0x1) +      // Left
                        (e.button & 0x2) * 2 +  // Right
                        (e.button & 0x4) / 2;   // Middle
            }

            $$$core$util$logging$$.Debug("onmousebutton " + (down ? "down" : "up") +
                      ", x: " + pos.x + ", y: " + pos.y + ", bmask: " + bmask);
            this.onmousebutton(pos.x, pos.y, down, bmask);

            $$$core$util$events$$stopEvent(e);
        }

        _handleMouseDown(e) {
            // Touch events have implicit capture
            if (e.type === "mousedown") {
                $$$core$util$events$$setCapture(this._target);
            }

            this._handleMouseButton(e, 1);
        }

        _handleMouseUp(e) {
            this._handleMouseButton(e, 0);
        }

        // Mouse wheel events are sent in steps over VNC. This means that the VNC
        // protocol can't handle a wheel event with specific distance or speed.
        // Therefor, if we get a lot of small mouse wheel events we combine them.
        _generateWheelStepX() {

            if (this._accumulatedWheelDeltaX < 0) {
                this.onmousebutton(this._pos.x, this._pos.y, 1, 1 << 5);
                this.onmousebutton(this._pos.x, this._pos.y, 0, 1 << 5);
            } else if (this._accumulatedWheelDeltaX > 0) {
                this.onmousebutton(this._pos.x, this._pos.y, 1, 1 << 6);
                this.onmousebutton(this._pos.x, this._pos.y, 0, 1 << 6);
            }

            this._accumulatedWheelDeltaX = 0;
        }

        _generateWheelStepY() {

            if (this._accumulatedWheelDeltaY < 0) {
                this.onmousebutton(this._pos.x, this._pos.y, 1, 1 << 3);
                this.onmousebutton(this._pos.x, this._pos.y, 0, 1 << 3);
            } else if (this._accumulatedWheelDeltaY > 0) {
                this.onmousebutton(this._pos.x, this._pos.y, 1, 1 << 4);
                this.onmousebutton(this._pos.x, this._pos.y, 0, 1 << 4);
            }

            this._accumulatedWheelDeltaY = 0;
        }

        _resetWheelStepTimers() {
            window.clearTimeout(this._wheelStepXTimer);
            window.clearTimeout(this._wheelStepYTimer);
            this._wheelStepXTimer = null;
            this._wheelStepYTimer = null;
        }

        _handleMouseWheel(e) {
            this._resetWheelStepTimers();

            this._updateMousePosition(e);

            let dX = e.deltaX;
            let dY = e.deltaY;

            // Pixel units unless it's non-zero.
            // Note that if deltamode is line or page won't matter since we aren't
            // sending the mouse wheel delta to the server anyway.
            // The difference between pixel and line can be important however since
            // we have a threshold that can be smaller than the line height.
            if (e.deltaMode !== 0) {
                dX *= $$input$mouse$$WHEEL_LINE_HEIGHT;
                dY *= $$input$mouse$$WHEEL_LINE_HEIGHT;
            }

            this._accumulatedWheelDeltaX += dX;
            this._accumulatedWheelDeltaY += dY;

            // Generate a mouse wheel step event when the accumulated delta
            // for one of the axes is large enough.
            // Small delta events that do not pass the threshold get sent
            // after a timeout.
            if (Math.abs(this._accumulatedWheelDeltaX) > $$input$mouse$$WHEEL_STEP) {
                this._generateWheelStepX();
            } else {
                this._wheelStepXTimer =
                    window.setTimeout(this._generateWheelStepX.bind(this),
                                      $$input$mouse$$WHEEL_STEP_TIMEOUT);
            }
            if (Math.abs(this._accumulatedWheelDeltaY) > $$input$mouse$$WHEEL_STEP) {
                this._generateWheelStepY();
            } else {
                this._wheelStepYTimer =
                    window.setTimeout(this._generateWheelStepY.bind(this),
                                      $$input$mouse$$WHEEL_STEP_TIMEOUT);
            }

            $$$core$util$events$$stopEvent(e);
        }

        _handleMouseMove(e) {
            this._updateMousePosition(e);
            this.onmousemove(this._pos.x, this._pos.y);
            $$$core$util$events$$stopEvent(e);
        }

        _handleMouseDisable(e) {
            /*
             * Stop propagation if inside canvas area
             * Note: This is only needed for the 'click' event as it fails
             *       to fire properly for the target element so we have
             *       to listen on the document element instead.
             */
            if (e.target == this._target) {
                $$$core$util$events$$stopEvent(e);
            }
        }

        // Update coordinates relative to target
        _updateMousePosition(e) {
            e = $$$core$util$events$$getPointerEvent(e);
            const bounds = this._target.getBoundingClientRect();
            let x;
            let y;
            // Clip to target bounds
            if (e.clientX < bounds.left) {
                x = 0;
            } else if (e.clientX >= bounds.right) {
                x = bounds.width - 1;
            } else {
                x = e.clientX - bounds.left;
            }
            if (e.clientY < bounds.top) {
                y = 0;
            } else if (e.clientY >= bounds.bottom) {
                y = bounds.height - 1;
            } else {
                y = e.clientY - bounds.top;
            }
            this._pos = {x: x, y: y};
        }

        // ===== PUBLIC METHODS =====

        grab() {
            if ($$$core$util$browser$$isTouchDevice) {
                this._target.addEventListener('touchstart', this._eventHandlers.mousedown);
                this._target.addEventListener('touchend', this._eventHandlers.mouseup);
                this._target.addEventListener('touchmove', this._eventHandlers.mousemove);
            }
            this._target.addEventListener('mousedown', this._eventHandlers.mousedown);
            this._target.addEventListener('mouseup', this._eventHandlers.mouseup);
            this._target.addEventListener('mousemove', this._eventHandlers.mousemove);
            this._target.addEventListener('wheel', this._eventHandlers.mousewheel);

            /* Prevent middle-click pasting (see above for why we bind to document) */
            document.addEventListener('click', this._eventHandlers.mousedisable);

            /* preventDefault() on mousedown doesn't stop this event for some
               reason so we have to explicitly block it */
            this._target.addEventListener('contextmenu', this._eventHandlers.mousedisable);
        }

        ungrab() {
            this._resetWheelStepTimers();

            if ($$$core$util$browser$$isTouchDevice) {
                this._target.removeEventListener('touchstart', this._eventHandlers.mousedown);
                this._target.removeEventListener('touchend', this._eventHandlers.mouseup);
                this._target.removeEventListener('touchmove', this._eventHandlers.mousemove);
            }
            this._target.removeEventListener('mousedown', this._eventHandlers.mousedown);
            this._target.removeEventListener('mouseup', this._eventHandlers.mouseup);
            this._target.removeEventListener('mousemove', this._eventHandlers.mousemove);
            this._target.removeEventListener('wheel', this._eventHandlers.mousewheel);

            document.removeEventListener('click', this._eventHandlers.mousedisable);

            this._target.removeEventListener('contextmenu', this._eventHandlers.mousedisable);
        }
    }

    var $$input$mouse$$default = $$input$mouse$$Mouse;

    const $$util$cursor$$useFallback = !$$$core$util$browser$$supportsCursorURIs || $$$core$util$browser$$isTouchDevice;

    class $$util$cursor$$Cursor {
        constructor() {
            this._target = null;

            this._showLocalCursor = false;

            this._canvas = document.createElement('canvas');

            if ($$util$cursor$$useFallback) {
                this._canvas.style.position = 'fixed';
                this._canvas.style.zIndex = '65535';
                this._canvas.style.pointerEvents = 'none';
                // Can't use "display" because of Firefox bug #1445997
                this._canvas.style.visibility = 'hidden';
                document.body.appendChild(this._canvas);
            }

            this._position = { x: 0, y: 0 };
            this._hotSpot = { x: 0, y: 0 };

            this._eventHandlers = {
                'mouseover': this._handleMouseOver.bind(this),
                'mouseleave': this._handleMouseLeave.bind(this),
                'mousemove': this._handleMouseMove.bind(this),
                'mouseup': this._handleMouseUp.bind(this),
                'touchstart': this._handleTouchStart.bind(this),
                'touchmove': this._handleTouchMove.bind(this),
                'touchend': this._handleTouchEnd.bind(this),
            };
        }

        attach(target) {
            if (this._target) {
                this.detach();
            }

            this._target = target;

            if ($$util$cursor$$useFallback) {
                // FIXME: These don't fire properly except for mouse
                ///       movement in IE. We want to also capture element
                //        movement, size changes, visibility, etc.
                const options = { capture: true, passive: true };
                this._target.addEventListener('mouseover', this._eventHandlers.mouseover, options);
                this._target.addEventListener('mouseleave', this._eventHandlers.mouseleave, options);
                this._target.addEventListener('mousemove', this._eventHandlers.mousemove, options);
                this._target.addEventListener('mouseup', this._eventHandlers.mouseup, options);

                // There is no "touchleave" so we monitor touchstart globally
                window.addEventListener('touchstart', this._eventHandlers.touchstart, options);
                this._target.addEventListener('touchmove', this._eventHandlers.touchmove, options);
                this._target.addEventListener('touchend', this._eventHandlers.touchend, options);
            }

            this.clear();
        }

        detach() {
            if ($$util$cursor$$useFallback) {
                const options = { capture: true, passive: true };
                this._target.removeEventListener('mouseover', this._eventHandlers.mouseover, options);
                this._target.removeEventListener('mouseleave', this._eventHandlers.mouseleave, options);
                this._target.removeEventListener('mousemove', this._eventHandlers.mousemove, options);
                this._target.removeEventListener('mouseup', this._eventHandlers.mouseup, options);

                window.removeEventListener('touchstart', this._eventHandlers.touchstart, options);
                this._target.removeEventListener('touchmove', this._eventHandlers.touchmove, options);
                this._target.removeEventListener('touchend', this._eventHandlers.touchend, options);
            }

            this._target = null;
        }

        change(rgba, hotx, hoty, w, h) {
            if ((w === 0) || (h === 0)) {
                this.clear();
                return;
            }

            this._position.x = this._position.x + this._hotSpot.x - hotx;
            this._position.y = this._position.y + this._hotSpot.y - hoty;
            this._hotSpot.x = hotx;
            this._hotSpot.y = hoty;

            let ctx = this._canvas.getContext('2d');

            this._canvas.width = w;
            this._canvas.height = h;

            let img;
            try {
                // IE doesn't support this
                img = new ImageData(new Uint8ClampedArray(rgba), w, h);
            } catch (ex) {
                img = ctx.createImageData(w, h);
                img.data.set(new Uint8ClampedArray(rgba));
            }
            ctx.clearRect(0, 0, w, h);
            ctx.putImageData(img, 0, 0);

            if ($$util$cursor$$useFallback) {
                this._updatePosition();
            } else {
                let url = this._canvas.toDataURL();
                this._target.style.cursor = 'url(' + url + ')' + hotx + ' ' + hoty + ', default';
            }
        }

        clear() {
            this._target.style.cursor = this._showLocalCursor ? 'default' : 'none';
            this._canvas.width = 0;
            this._canvas.height = 0;
            this._position.x = this._position.x + this._hotSpot.x;
            this._position.y = this._position.y + this._hotSpot.y;
            this._hotSpot.x = 0;
            this._hotSpot.y = 0;
        }

        setLocalCursor(cursor) {
            this._showLocalCursor = cursor;
            this._updateLocalCursor();
        }

        _handleMouseOver(event) {
            // This event could be because we're entering the target, or
            // moving around amongst its sub elements. Let the move handler
            // sort things out.
            this._handleMouseMove(event);
        }

        _handleMouseLeave(event) {
            this._hideCursor();
        }

        _handleMouseMove(event) {
            this._updateVisibility(event.target);

            this._position.x = event.clientX - this._hotSpot.x;
            this._position.y = event.clientY - this._hotSpot.y;

            this._updatePosition();
        }

        _handleMouseUp(event) {
            // We might get this event because of a drag operation that
            // moved outside of the target. Check what's under the cursor
            // now and adjust visibility based on that.
            let target = document.elementFromPoint(event.clientX, event.clientY);
            this._updateVisibility(target);
        }

        _handleTouchStart(event) {
            // Just as for mouseover, we let the move handler deal with it
            this._handleTouchMove(event);
        }

        _handleTouchMove(event) {
            this._updateVisibility(event.target);

            this._position.x = event.changedTouches[0].clientX - this._hotSpot.x;
            this._position.y = event.changedTouches[0].clientY - this._hotSpot.y;

            this._updatePosition();
        }

        _handleTouchEnd(event) {
            // Same principle as for mouseup
            let target = document.elementFromPoint(event.changedTouches[0].clientX,
                                                   event.changedTouches[0].clientY);
            this._updateVisibility(target);
        }

        _showCursor() {
            if (this._canvas.style.visibility === 'hidden') {
                this._canvas.style.visibility = '';
            }
        }

        _hideCursor() {
            if (this._canvas.style.visibility !== 'hidden') {
                this._canvas.style.visibility = 'hidden';
            }
        }

        // Should we currently display the cursor?
        // (i.e. are we over the target, or a child of the target without a
        // different cursor set)
        _shouldShowCursor(target) {
            // Easy case
            if (target === this._target) {
                return true;
            }
            // Other part of the DOM?
            if (!this._target.contains(target)) {
                return false;
            }
            // Has the child its own cursor?
            // FIXME: How can we tell that a sub element has an
            //        explicit "cursor: none;"?
            if (window.getComputedStyle(target).cursor !== 'none') {
                return false;
            }
            return true;
        }

        _updateVisibility(target) {
            if (this._shouldShowCursor(target)) {
                this._showCursor();
            } else {
                this._hideCursor();
            }
        }

        _updatePosition() {
            this._canvas.style.left = this._position.x + "px";
            this._canvas.style.top = this._position.y + "px";
        }

        _updateLocalCursor() {
            if (this._target)
                this._target.style.cursor = this._showLocalCursor ? 'default' : 'none';
        }

    }

    var $$util$cursor$$default = $$util$cursor$$Cursor;

    // this has performance issues in some versions Chromium, and
    // doesn't gain a tremendous amount of performance increase in Firefox
    // at the moment.  It may be valuable to turn it on in the future.
    const $$websock$$ENABLE_COPYWITHIN = false;
    const $$websock$$MAX_RQ_GROW_SIZE = 40 * 1024 * 1024;  // 40 MiB

    class $$websock$$Websock {
        constructor() {
            this._websocket = null;  // WebSocket object

            this._rQi = 0;           // Receive queue index
            this._rQlen = 0;         // Next write position in the receive queue
            this._rQbufferSize = 1024 * 1024 * 4; // Receive queue buffer size (4 MiB)
            this._rQmax = this._rQbufferSize / 8;
            // called in init: this._rQ = new Uint8Array(this._rQbufferSize);
            this._rQ = null; // Receive queue

            this._sQbufferSize = 1024 * 10;  // 10 KiB
            // called in init: this._sQ = new Uint8Array(this._sQbufferSize);
            this._sQlen = 0;
            this._sQ = null;  // Send queue

            this._eventHandlers = {
                message: () => {},
                open: () => {},
                close: () => {},
                error: () => {}
            };
        }

        // Getters and Setters
        get sQ() {
            return this._sQ;
        }

        get rQ() {
            return this._rQ;
        }

        get rQi() {
            return this._rQi;
        }

        set rQi(val) {
            this._rQi = val;
        }

        // Receive Queue
        get rQlen() {
            return this._rQlen - this._rQi;
        }

        rQpeek8() {
            return this._rQ[this._rQi];
        }

        rQskipBytes(bytes) {
            this._rQi += bytes;
        }

        rQshift8() {
            return this._rQshift(1);
        }

        rQshift16() {
            return this._rQshift(2);
        }

        rQshift32() {
            return this._rQshift(4);
        }

        // TODO(directxman12): test performance with these vs a DataView
        _rQshift(bytes) {
            let res = 0;
            for (let byte = bytes - 1; byte >= 0; byte--) {
                res += this._rQ[this._rQi++] << (byte * 8);
            }
            return res;
        }

        rQshiftStr(len) {
            if (typeof(len) === 'undefined') { len = this.rQlen; }
            let str = "";
            // Handle large arrays in steps to avoid long strings on the stack
            for (let i = 0; i < len; i += 4096) {
                let part = this.rQshiftBytes(Math.min(4096, len - i));
                str += String.fromCharCode.apply(null, part);
            }
            return str;
        }

        rQshiftBytes(len) {
            if (typeof(len) === 'undefined') { len = this.rQlen; }
            this._rQi += len;
            return new Uint8Array(this._rQ.buffer, this._rQi - len, len);
        }

        rQshiftTo(target, len) {
            if (len === undefined) { len = this.rQlen; }
            // TODO: make this just use set with views when using a ArrayBuffer to store the rQ
            target.set(new Uint8Array(this._rQ.buffer, this._rQi, len));
            this._rQi += len;
        }

        rQslice(start, end = this.rQlen) {
            return new Uint8Array(this._rQ.buffer, this._rQi + start, end - start);
        }

        // Check to see if we must wait for 'num' bytes (default to FBU.bytes)
        // to be available in the receive queue. Return true if we need to
        // wait (and possibly print a debug message), otherwise false.
        rQwait(msg, num, goback) {
            if (this.rQlen < num) {
                if (goback) {
                    if (this._rQi < goback) {
                        throw new Error("rQwait cannot backup " + goback + " bytes");
                    }
                    this._rQi -= goback;
                }
                return true; // true means need more data
            }
            return false;
        }

        // Send Queue

        flush() {
            if (this._sQlen > 0 && this._websocket.readyState === WebSocket.OPEN) {
                this._websocket.send(this._encode_message());
                this._sQlen = 0;
            }
        }

        send(arr) {
            this._sQ.set(arr, this._sQlen);
            this._sQlen += arr.length;
            this.flush();
        }

        send_string(str) {
            this.send(str.split('').map(chr => chr.charCodeAt(0)));
        }

        // Event Handlers
        off(evt) {
            this._eventHandlers[evt] = () => {};
        }

        on(evt, handler) {
            this._eventHandlers[evt] = handler;
        }

        _allocate_buffers() {
            this._rQ = new Uint8Array(this._rQbufferSize);
            this._sQ = new Uint8Array(this._sQbufferSize);
        }

        init() {
            this._allocate_buffers();
            this._rQi = 0;
            this._websocket = null;
        }

        open(uri, protocols) {
            this.init();

            this._websocket = new WebSocket(uri, protocols);
            this._websocket.binaryType = 'arraybuffer';

            this._websocket.onmessage = this._recv_message.bind(this);
            this._websocket.onopen = () => {
                $$$core$util$logging$$.Debug('>> WebSock.onopen');
                if (this._websocket.protocol) {
                    $$$core$util$logging$$.Info("Server choose sub-protocol: " + this._websocket.protocol);
                }

                this._eventHandlers.open();
                $$$core$util$logging$$.Debug("<< WebSock.onopen");
            };
            this._websocket.onclose = (e) => {
                $$$core$util$logging$$.Debug(">> WebSock.onclose");
                this._eventHandlers.close(e);
                $$$core$util$logging$$.Debug("<< WebSock.onclose");
            };
            this._websocket.onerror = (e) => {
                $$$core$util$logging$$.Debug(">> WebSock.onerror: " + e);
                this._eventHandlers.error(e);
                $$$core$util$logging$$.Debug("<< WebSock.onerror: " + e);
            };
        }

        close() {
            if (this._websocket) {
                if ((this._websocket.readyState === WebSocket.OPEN) ||
                        (this._websocket.readyState === WebSocket.CONNECTING)) {
                    $$$core$util$logging$$.Info("Closing WebSocket connection");
                    this._websocket.close();
                }

                this._websocket.onmessage = () => {};
            }
        }

        // private methods
        _encode_message() {
            // Put in a binary arraybuffer
            // according to the spec, you can send ArrayBufferViews with the send method
            return new Uint8Array(this._sQ.buffer, 0, this._sQlen);
        }

        _expand_compact_rQ(min_fit) {
            const resizeNeeded = min_fit || this.rQlen > this._rQbufferSize / 2;
            if (resizeNeeded) {
                if (!min_fit) {
                    // just double the size if we need to do compaction
                    this._rQbufferSize *= 2;
                } else {
                    // otherwise, make sure we satisy rQlen - rQi + min_fit < rQbufferSize / 8
                    this._rQbufferSize = (this.rQlen + min_fit) * 8;
                }
            }

            // we don't want to grow unboundedly
            if (this._rQbufferSize > $$websock$$MAX_RQ_GROW_SIZE) {
                this._rQbufferSize = $$websock$$MAX_RQ_GROW_SIZE;
                if (this._rQbufferSize - this.rQlen < min_fit) {
                    throw new Error("Receive Queue buffer exceeded " + $$websock$$MAX_RQ_GROW_SIZE + " bytes, and the new message could not fit");
                }
            }

            if (resizeNeeded) {
                const old_rQbuffer = this._rQ.buffer;
                this._rQmax = this._rQbufferSize / 8;
                this._rQ = new Uint8Array(this._rQbufferSize);
                this._rQ.set(new Uint8Array(old_rQbuffer, this._rQi));
            } else {
                if ($$websock$$ENABLE_COPYWITHIN) {
                    this._rQ.copyWithin(0, this._rQi);
                } else {
                    this._rQ.set(new Uint8Array(this._rQ.buffer, this._rQi));
                }
            }

            this._rQlen = this._rQlen - this._rQi;
            this._rQi = 0;
        }

        _decode_message(data) {
            // push arraybuffer values onto the end
            const u8 = new Uint8Array(data);
            if (u8.length > this._rQbufferSize - this._rQlen) {
                this._expand_compact_rQ(u8.length);
            }
            this._rQ.set(u8, this._rQlen);
            this._rQlen += u8.length;
        }

        _recv_message(e) {
            this._decode_message(e.data);
            if (this.rQlen > 0) {
                this._eventHandlers.message();
                // Compact the receive queue
                if (this._rQlen == this._rQi) {
                    this._rQlen = 0;
                    this._rQi = 0;
                } else if (this._rQlen > this._rQmax) {
                    this._expand_compact_rQ();
                }
            } else {
                $$$core$util$logging$$.Debug("Ignoring empty message");
            }
        }
    }

    var $$websock$$default = $$websock$$Websock;
    /*
     * Ported from Flashlight VNC ActionScript implementation:
     *     http://www.wizhelp.com/flashlight-vnc/
     *
     * Full attribution follows:
     *
     * -------------------------------------------------------------------------
     *
     * This DES class has been extracted from package Acme.Crypto for use in VNC.
     * The unnecessary odd parity code has been removed.
     *
     * These changes are:
     *  Copyright (C) 1999 AT&T Laboratories Cambridge.  All Rights Reserved.
     *
     * This software is distributed in the hope that it will be useful,
     * but WITHOUT ANY WARRANTY; without even the implied warranty of
     * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.
     *

     * DesCipher - the DES encryption method
     *
     * The meat of this code is by Dave Zimmerman <dzimm@widget.com>, and is:
     *
     * Copyright (c) 1996 Widget Workshop, Inc. All Rights Reserved.
     *
     * Permission to use, copy, modify, and distribute this software
     * and its documentation for NON-COMMERCIAL or COMMERCIAL purposes and
     * without fee is hereby granted, provided that this copyright notice is kept
     * intact.
     *
     * WIDGET WORKSHOP MAKES NO REPRESENTATIONS OR WARRANTIES ABOUT THE SUITABILITY
     * OF THE SOFTWARE, EITHER EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED
     * TO THE IMPLIED WARRANTIES OF MERCHANTABILITY, FITNESS FOR A
     * PARTICULAR PURPOSE, OR NON-INFRINGEMENT. WIDGET WORKSHOP SHALL NOT BE LIABLE
     * FOR ANY DAMAGES SUFFERED BY LICENSEE AS A RESULT OF USING, MODIFYING OR
     * DISTRIBUTING THIS SOFTWARE OR ITS DERIVATIVES.
     *
     * THIS SOFTWARE IS NOT DESIGNED OR INTENDED FOR USE OR RESALE AS ON-LINE
     * CONTROL EQUIPMENT IN HAZARDOUS ENVIRONMENTS REQUIRING FAIL-SAFE
     * PERFORMANCE, SUCH AS IN THE OPERATION OF NUCLEAR FACILITIES, AIRCRAFT
     * NAVIGATION OR COMMUNICATION SYSTEMS, AIR TRAFFIC CONTROL, DIRECT LIFE
     * SUPPORT MACHINES, OR WEAPONS SYSTEMS, IN WHICH THE FAILURE OF THE
     * SOFTWARE COULD LEAD DIRECTLY TO DEATH, PERSONAL INJURY, OR SEVERE
     * PHYSICAL OR ENVIRONMENTAL DAMAGE ("HIGH RISK ACTIVITIES").  WIDGET WORKSHOP
     * SPECIFICALLY DISCLAIMS ANY EXPRESS OR IMPLIED WARRANTY OF FITNESS FOR
     * HIGH RISK ACTIVITIES.
     *
     *
     * The rest is:
     *
     * Copyright (C) 1996 by Jef Poskanzer <jef@acme.com>.  All rights reserved.
     *
     * Redistribution and use in source and binary forms, with or without
     * modification, are permitted provided that the following conditions
     * are met:
     * 1. Redistributions of source code must retain the above copyright
     *    notice, this list of conditions and the following disclaimer.
     * 2. Redistributions in binary form must reproduce the above copyright
     *    notice, this list of conditions and the following disclaimer in the
     *    documentation and/or other materials provided with the distribution.
     *
     * THIS SOFTWARE IS PROVIDED BY THE AUTHOR AND CONTRIBUTORS ``AS IS'' AND
     * ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
     * IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
     * ARE DISCLAIMED.  IN NO EVENT SHALL THE AUTHOR OR CONTRIBUTORS BE LIABLE
     * FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
     * DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS
     * OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION)
     * HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT
     * LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY
     * OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF
     * SUCH DAMAGE.
     *
     * Visit the ACME Labs Java page for up-to-date versions of this and other
     * fine Java utilities: http://www.acme.com/java/
     */

    /* eslint-disable comma-spacing */

    // Tables, permutations, S-boxes, etc.
    const $$des$$PC2 = [13,16,10,23, 0, 4, 2,27,14, 5,20, 9,22,18,11, 3,
                 25, 7,15, 6,26,19,12, 1,40,51,30,36,46,54,29,39,
                 50,44,32,47,43,48,38,55,33,52,45,41,49,35,28,31 ],
        $$des$$totrot = [ 1, 2, 4, 6, 8,10,12,14,15,17,19,21,23,25,27,28];

    const $$des$$z = 0x0;
    let $$des$$a,$$des$$b,$$des$$c,$$des$$d,$$des$$e,$$des$$f;
    $$des$$a=1<<16;$$des$$b=1<<24;$$des$$c=$$des$$a|$$des$$b;$$des$$d=1<<2;$$des$$e=1<<10;$$des$$f=$$des$$d|$$des$$e;
    const $$des$$SP1 = [$$des$$c|$$des$$e,$$des$$z|$$des$$z,$$des$$a|$$des$$z,$$des$$c|$$des$$f,$$des$$c|$$des$$d,$$des$$a|$$des$$f,$$des$$z|$$des$$d,$$des$$a|$$des$$z,$$des$$z|$$des$$e,$$des$$c|$$des$$e,$$des$$c|$$des$$f,$$des$$z|$$des$$e,$$des$$b|$$des$$f,$$des$$c|$$des$$d,$$des$$b|$$des$$z,$$des$$z|$$des$$d,
                 $$des$$z|$$des$$f,$$des$$b|$$des$$e,$$des$$b|$$des$$e,$$des$$a|$$des$$e,$$des$$a|$$des$$e,$$des$$c|$$des$$z,$$des$$c|$$des$$z,$$des$$b|$$des$$f,$$des$$a|$$des$$d,$$des$$b|$$des$$d,$$des$$b|$$des$$d,$$des$$a|$$des$$d,$$des$$z|$$des$$z,$$des$$z|$$des$$f,$$des$$a|$$des$$f,$$des$$b|$$des$$z,
                 $$des$$a|$$des$$z,$$des$$c|$$des$$f,$$des$$z|$$des$$d,$$des$$c|$$des$$z,$$des$$c|$$des$$e,$$des$$b|$$des$$z,$$des$$b|$$des$$z,$$des$$z|$$des$$e,$$des$$c|$$des$$d,$$des$$a|$$des$$z,$$des$$a|$$des$$e,$$des$$b|$$des$$d,$$des$$z|$$des$$e,$$des$$z|$$des$$d,$$des$$b|$$des$$f,$$des$$a|$$des$$f,
                 $$des$$c|$$des$$f,$$des$$a|$$des$$d,$$des$$c|$$des$$z,$$des$$b|$$des$$f,$$des$$b|$$des$$d,$$des$$z|$$des$$f,$$des$$a|$$des$$f,$$des$$c|$$des$$e,$$des$$z|$$des$$f,$$des$$b|$$des$$e,$$des$$b|$$des$$e,$$des$$z|$$des$$z,$$des$$a|$$des$$d,$$des$$a|$$des$$e,$$des$$z|$$des$$z,$$des$$c|$$des$$d];
    $$des$$a=1<<20;$$des$$b=1<<31;$$des$$c=$$des$$a|$$des$$b;$$des$$d=1<<5;$$des$$e=1<<15;$$des$$f=$$des$$d|$$des$$e;
    const $$des$$SP2 = [$$des$$c|$$des$$f,$$des$$b|$$des$$e,$$des$$z|$$des$$e,$$des$$a|$$des$$f,$$des$$a|$$des$$z,$$des$$z|$$des$$d,$$des$$c|$$des$$d,$$des$$b|$$des$$f,$$des$$b|$$des$$d,$$des$$c|$$des$$f,$$des$$c|$$des$$e,$$des$$b|$$des$$z,$$des$$b|$$des$$e,$$des$$a|$$des$$z,$$des$$z|$$des$$d,$$des$$c|$$des$$d,
                 $$des$$a|$$des$$e,$$des$$a|$$des$$d,$$des$$b|$$des$$f,$$des$$z|$$des$$z,$$des$$b|$$des$$z,$$des$$z|$$des$$e,$$des$$a|$$des$$f,$$des$$c|$$des$$z,$$des$$a|$$des$$d,$$des$$b|$$des$$d,$$des$$z|$$des$$z,$$des$$a|$$des$$e,$$des$$z|$$des$$f,$$des$$c|$$des$$e,$$des$$c|$$des$$z,$$des$$z|$$des$$f,
                 $$des$$z|$$des$$z,$$des$$a|$$des$$f,$$des$$c|$$des$$d,$$des$$a|$$des$$z,$$des$$b|$$des$$f,$$des$$c|$$des$$z,$$des$$c|$$des$$e,$$des$$z|$$des$$e,$$des$$c|$$des$$z,$$des$$b|$$des$$e,$$des$$z|$$des$$d,$$des$$c|$$des$$f,$$des$$a|$$des$$f,$$des$$z|$$des$$d,$$des$$z|$$des$$e,$$des$$b|$$des$$z,
                 $$des$$z|$$des$$f,$$des$$c|$$des$$e,$$des$$a|$$des$$z,$$des$$b|$$des$$d,$$des$$a|$$des$$d,$$des$$b|$$des$$f,$$des$$b|$$des$$d,$$des$$a|$$des$$d,$$des$$a|$$des$$e,$$des$$z|$$des$$z,$$des$$b|$$des$$e,$$des$$z|$$des$$f,$$des$$b|$$des$$z,$$des$$c|$$des$$d,$$des$$c|$$des$$f,$$des$$a|$$des$$e];
    $$des$$a=1<<17;$$des$$b=1<<27;$$des$$c=$$des$$a|$$des$$b;$$des$$d=1<<3;$$des$$e=1<<9;$$des$$f=$$des$$d|$$des$$e;
    const $$des$$SP3 = [$$des$$z|$$des$$f,$$des$$c|$$des$$e,$$des$$z|$$des$$z,$$des$$c|$$des$$d,$$des$$b|$$des$$e,$$des$$z|$$des$$z,$$des$$a|$$des$$f,$$des$$b|$$des$$e,$$des$$a|$$des$$d,$$des$$b|$$des$$d,$$des$$b|$$des$$d,$$des$$a|$$des$$z,$$des$$c|$$des$$f,$$des$$a|$$des$$d,$$des$$c|$$des$$z,$$des$$z|$$des$$f,
                 $$des$$b|$$des$$z,$$des$$z|$$des$$d,$$des$$c|$$des$$e,$$des$$z|$$des$$e,$$des$$a|$$des$$e,$$des$$c|$$des$$z,$$des$$c|$$des$$d,$$des$$a|$$des$$f,$$des$$b|$$des$$f,$$des$$a|$$des$$e,$$des$$a|$$des$$z,$$des$$b|$$des$$f,$$des$$z|$$des$$d,$$des$$c|$$des$$f,$$des$$z|$$des$$e,$$des$$b|$$des$$z,
                 $$des$$c|$$des$$e,$$des$$b|$$des$$z,$$des$$a|$$des$$d,$$des$$z|$$des$$f,$$des$$a|$$des$$z,$$des$$c|$$des$$e,$$des$$b|$$des$$e,$$des$$z|$$des$$z,$$des$$z|$$des$$e,$$des$$a|$$des$$d,$$des$$c|$$des$$f,$$des$$b|$$des$$e,$$des$$b|$$des$$d,$$des$$z|$$des$$e,$$des$$z|$$des$$z,$$des$$c|$$des$$d,
                 $$des$$b|$$des$$f,$$des$$a|$$des$$z,$$des$$b|$$des$$z,$$des$$c|$$des$$f,$$des$$z|$$des$$d,$$des$$a|$$des$$f,$$des$$a|$$des$$e,$$des$$b|$$des$$d,$$des$$c|$$des$$z,$$des$$b|$$des$$f,$$des$$z|$$des$$f,$$des$$c|$$des$$z,$$des$$a|$$des$$f,$$des$$z|$$des$$d,$$des$$c|$$des$$d,$$des$$a|$$des$$e];
    $$des$$a=1<<13;$$des$$b=1<<23;$$des$$c=$$des$$a|$$des$$b;$$des$$d=1<<0;$$des$$e=1<<7;$$des$$f=$$des$$d|$$des$$e;
    const $$des$$SP4 = [$$des$$c|$$des$$d,$$des$$a|$$des$$f,$$des$$a|$$des$$f,$$des$$z|$$des$$e,$$des$$c|$$des$$e,$$des$$b|$$des$$f,$$des$$b|$$des$$d,$$des$$a|$$des$$d,$$des$$z|$$des$$z,$$des$$c|$$des$$z,$$des$$c|$$des$$z,$$des$$c|$$des$$f,$$des$$z|$$des$$f,$$des$$z|$$des$$z,$$des$$b|$$des$$e,$$des$$b|$$des$$d,
                 $$des$$z|$$des$$d,$$des$$a|$$des$$z,$$des$$b|$$des$$z,$$des$$c|$$des$$d,$$des$$z|$$des$$e,$$des$$b|$$des$$z,$$des$$a|$$des$$d,$$des$$a|$$des$$e,$$des$$b|$$des$$f,$$des$$z|$$des$$d,$$des$$a|$$des$$e,$$des$$b|$$des$$e,$$des$$a|$$des$$z,$$des$$c|$$des$$e,$$des$$c|$$des$$f,$$des$$z|$$des$$f,
                 $$des$$b|$$des$$e,$$des$$b|$$des$$d,$$des$$c|$$des$$z,$$des$$c|$$des$$f,$$des$$z|$$des$$f,$$des$$z|$$des$$z,$$des$$z|$$des$$z,$$des$$c|$$des$$z,$$des$$a|$$des$$e,$$des$$b|$$des$$e,$$des$$b|$$des$$f,$$des$$z|$$des$$d,$$des$$c|$$des$$d,$$des$$a|$$des$$f,$$des$$a|$$des$$f,$$des$$z|$$des$$e,
                 $$des$$c|$$des$$f,$$des$$z|$$des$$f,$$des$$z|$$des$$d,$$des$$a|$$des$$z,$$des$$b|$$des$$d,$$des$$a|$$des$$d,$$des$$c|$$des$$e,$$des$$b|$$des$$f,$$des$$a|$$des$$d,$$des$$a|$$des$$e,$$des$$b|$$des$$z,$$des$$c|$$des$$d,$$des$$z|$$des$$e,$$des$$b|$$des$$z,$$des$$a|$$des$$z,$$des$$c|$$des$$e];
    $$des$$a=1<<25;$$des$$b=1<<30;$$des$$c=$$des$$a|$$des$$b;$$des$$d=1<<8;$$des$$e=1<<19;$$des$$f=$$des$$d|$$des$$e;
    const $$des$$SP5 = [$$des$$z|$$des$$d,$$des$$a|$$des$$f,$$des$$a|$$des$$e,$$des$$c|$$des$$d,$$des$$z|$$des$$e,$$des$$z|$$des$$d,$$des$$b|$$des$$z,$$des$$a|$$des$$e,$$des$$b|$$des$$f,$$des$$z|$$des$$e,$$des$$a|$$des$$d,$$des$$b|$$des$$f,$$des$$c|$$des$$d,$$des$$c|$$des$$e,$$des$$z|$$des$$f,$$des$$b|$$des$$z,
                 $$des$$a|$$des$$z,$$des$$b|$$des$$e,$$des$$b|$$des$$e,$$des$$z|$$des$$z,$$des$$b|$$des$$d,$$des$$c|$$des$$f,$$des$$c|$$des$$f,$$des$$a|$$des$$d,$$des$$c|$$des$$e,$$des$$b|$$des$$d,$$des$$z|$$des$$z,$$des$$c|$$des$$z,$$des$$a|$$des$$f,$$des$$a|$$des$$z,$$des$$c|$$des$$z,$$des$$z|$$des$$f,
                 $$des$$z|$$des$$e,$$des$$c|$$des$$d,$$des$$z|$$des$$d,$$des$$a|$$des$$z,$$des$$b|$$des$$z,$$des$$a|$$des$$e,$$des$$c|$$des$$d,$$des$$b|$$des$$f,$$des$$a|$$des$$d,$$des$$b|$$des$$z,$$des$$c|$$des$$e,$$des$$a|$$des$$f,$$des$$b|$$des$$f,$$des$$z|$$des$$d,$$des$$a|$$des$$z,$$des$$c|$$des$$e,
                 $$des$$c|$$des$$f,$$des$$z|$$des$$f,$$des$$c|$$des$$z,$$des$$c|$$des$$f,$$des$$a|$$des$$e,$$des$$z|$$des$$z,$$des$$b|$$des$$e,$$des$$c|$$des$$z,$$des$$z|$$des$$f,$$des$$a|$$des$$d,$$des$$b|$$des$$d,$$des$$z|$$des$$e,$$des$$z|$$des$$z,$$des$$b|$$des$$e,$$des$$a|$$des$$f,$$des$$b|$$des$$d];
    $$des$$a=1<<22;$$des$$b=1<<29;$$des$$c=$$des$$a|$$des$$b;$$des$$d=1<<4;$$des$$e=1<<14;$$des$$f=$$des$$d|$$des$$e;
    const $$des$$SP6 = [$$des$$b|$$des$$d,$$des$$c|$$des$$z,$$des$$z|$$des$$e,$$des$$c|$$des$$f,$$des$$c|$$des$$z,$$des$$z|$$des$$d,$$des$$c|$$des$$f,$$des$$a|$$des$$z,$$des$$b|$$des$$e,$$des$$a|$$des$$f,$$des$$a|$$des$$z,$$des$$b|$$des$$d,$$des$$a|$$des$$d,$$des$$b|$$des$$e,$$des$$b|$$des$$z,$$des$$z|$$des$$f,
                 $$des$$z|$$des$$z,$$des$$a|$$des$$d,$$des$$b|$$des$$f,$$des$$z|$$des$$e,$$des$$a|$$des$$e,$$des$$b|$$des$$f,$$des$$z|$$des$$d,$$des$$c|$$des$$d,$$des$$c|$$des$$d,$$des$$z|$$des$$z,$$des$$a|$$des$$f,$$des$$c|$$des$$e,$$des$$z|$$des$$f,$$des$$a|$$des$$e,$$des$$c|$$des$$e,$$des$$b|$$des$$z,
                 $$des$$b|$$des$$e,$$des$$z|$$des$$d,$$des$$c|$$des$$d,$$des$$a|$$des$$e,$$des$$c|$$des$$f,$$des$$a|$$des$$z,$$des$$z|$$des$$f,$$des$$b|$$des$$d,$$des$$a|$$des$$z,$$des$$b|$$des$$e,$$des$$b|$$des$$z,$$des$$z|$$des$$f,$$des$$b|$$des$$d,$$des$$c|$$des$$f,$$des$$a|$$des$$e,$$des$$c|$$des$$z,
                 $$des$$a|$$des$$f,$$des$$c|$$des$$e,$$des$$z|$$des$$z,$$des$$c|$$des$$d,$$des$$z|$$des$$d,$$des$$z|$$des$$e,$$des$$c|$$des$$z,$$des$$a|$$des$$f,$$des$$z|$$des$$e,$$des$$a|$$des$$d,$$des$$b|$$des$$f,$$des$$z|$$des$$z,$$des$$c|$$des$$e,$$des$$b|$$des$$z,$$des$$a|$$des$$d,$$des$$b|$$des$$f];
    $$des$$a=1<<21;$$des$$b=1<<26;$$des$$c=$$des$$a|$$des$$b;$$des$$d=1<<1;$$des$$e=1<<11;$$des$$f=$$des$$d|$$des$$e;
    const $$des$$SP7 = [$$des$$a|$$des$$z,$$des$$c|$$des$$d,$$des$$b|$$des$$f,$$des$$z|$$des$$z,$$des$$z|$$des$$e,$$des$$b|$$des$$f,$$des$$a|$$des$$f,$$des$$c|$$des$$e,$$des$$c|$$des$$f,$$des$$a|$$des$$z,$$des$$z|$$des$$z,$$des$$b|$$des$$d,$$des$$z|$$des$$d,$$des$$b|$$des$$z,$$des$$c|$$des$$d,$$des$$z|$$des$$f,
                 $$des$$b|$$des$$e,$$des$$a|$$des$$f,$$des$$a|$$des$$d,$$des$$b|$$des$$e,$$des$$b|$$des$$d,$$des$$c|$$des$$z,$$des$$c|$$des$$e,$$des$$a|$$des$$d,$$des$$c|$$des$$z,$$des$$z|$$des$$e,$$des$$z|$$des$$f,$$des$$c|$$des$$f,$$des$$a|$$des$$e,$$des$$z|$$des$$d,$$des$$b|$$des$$z,$$des$$a|$$des$$e,
                 $$des$$b|$$des$$z,$$des$$a|$$des$$e,$$des$$a|$$des$$z,$$des$$b|$$des$$f,$$des$$b|$$des$$f,$$des$$c|$$des$$d,$$des$$c|$$des$$d,$$des$$z|$$des$$d,$$des$$a|$$des$$d,$$des$$b|$$des$$z,$$des$$b|$$des$$e,$$des$$a|$$des$$z,$$des$$c|$$des$$e,$$des$$z|$$des$$f,$$des$$a|$$des$$f,$$des$$c|$$des$$e,
                 $$des$$z|$$des$$f,$$des$$b|$$des$$d,$$des$$c|$$des$$f,$$des$$c|$$des$$z,$$des$$a|$$des$$e,$$des$$z|$$des$$z,$$des$$z|$$des$$d,$$des$$c|$$des$$f,$$des$$z|$$des$$z,$$des$$a|$$des$$f,$$des$$c|$$des$$z,$$des$$z|$$des$$e,$$des$$b|$$des$$d,$$des$$b|$$des$$e,$$des$$z|$$des$$e,$$des$$a|$$des$$d];
    $$des$$a=1<<18;$$des$$b=1<<28;$$des$$c=$$des$$a|$$des$$b;$$des$$d=1<<6;$$des$$e=1<<12;$$des$$f=$$des$$d|$$des$$e;
    const $$des$$SP8 = [$$des$$b|$$des$$f,$$des$$z|$$des$$e,$$des$$a|$$des$$z,$$des$$c|$$des$$f,$$des$$b|$$des$$z,$$des$$b|$$des$$f,$$des$$z|$$des$$d,$$des$$b|$$des$$z,$$des$$a|$$des$$d,$$des$$c|$$des$$z,$$des$$c|$$des$$f,$$des$$a|$$des$$e,$$des$$c|$$des$$e,$$des$$a|$$des$$f,$$des$$z|$$des$$e,$$des$$z|$$des$$d,
                 $$des$$c|$$des$$z,$$des$$b|$$des$$d,$$des$$b|$$des$$e,$$des$$z|$$des$$f,$$des$$a|$$des$$e,$$des$$a|$$des$$d,$$des$$c|$$des$$d,$$des$$c|$$des$$e,$$des$$z|$$des$$f,$$des$$z|$$des$$z,$$des$$z|$$des$$z,$$des$$c|$$des$$d,$$des$$b|$$des$$d,$$des$$b|$$des$$e,$$des$$a|$$des$$f,$$des$$a|$$des$$z,
                 $$des$$a|$$des$$f,$$des$$a|$$des$$z,$$des$$c|$$des$$e,$$des$$z|$$des$$e,$$des$$z|$$des$$d,$$des$$c|$$des$$d,$$des$$z|$$des$$e,$$des$$a|$$des$$f,$$des$$b|$$des$$e,$$des$$z|$$des$$d,$$des$$b|$$des$$d,$$des$$c|$$des$$z,$$des$$c|$$des$$d,$$des$$b|$$des$$z,$$des$$a|$$des$$z,$$des$$b|$$des$$f,
                 $$des$$z|$$des$$z,$$des$$c|$$des$$f,$$des$$a|$$des$$d,$$des$$b|$$des$$d,$$des$$c|$$des$$z,$$des$$b|$$des$$e,$$des$$b|$$des$$f,$$des$$z|$$des$$z,$$des$$c|$$des$$f,$$des$$a|$$des$$e,$$des$$a|$$des$$e,$$des$$z|$$des$$f,$$des$$z|$$des$$f,$$des$$a|$$des$$d,$$des$$b|$$des$$z,$$des$$c|$$des$$e];

    class $$des$$DES {
        constructor(password) {
            this.keys = [];

            // Set the key.
            const pc1m = [], pcr = [], kn = [];

            for (let j = 0, l = 56; j < 56; ++j, l -= 8) {
                l += l < -5 ? 65 : l < -3 ? 31 : l < -1 ? 63 : l === 27 ? 35 : 0; // PC1
                const m = l & 0x7;
                pc1m[j] = ((password[l >>> 3] & (1<<m)) !== 0) ? 1: 0;
            }

            for (let i = 0; i < 16; ++i) {
                const m = i << 1;
                const n = m + 1;
                kn[m] = kn[n] = 0;
                for (let o = 28; o < 59; o += 28) {
                    for (let j = o - 28; j < o; ++j) {
                        const l = j + $$des$$totrot[i];
                        pcr[j] = l < o ? pc1m[l] : pc1m[l - 28];
                    }
                }
                for (let j = 0; j < 24; ++j) {
                    if (pcr[$$des$$PC2[j]] !== 0) {
                        kn[m] |= 1 << (23 - j);
                    }
                    if (pcr[$$des$$PC2[j + 24]] !== 0) {
                        kn[n] |= 1 << (23 - j);
                    }
                }
            }

            // cookey
            for (let i = 0, rawi = 0, KnLi = 0; i < 16; ++i) {
                const raw0 = kn[rawi++];
                const raw1 = kn[rawi++];
                this.keys[KnLi] = (raw0 & 0x00fc0000) << 6;
                this.keys[KnLi] |= (raw0 & 0x00000fc0) << 10;
                this.keys[KnLi] |= (raw1 & 0x00fc0000) >>> 10;
                this.keys[KnLi] |= (raw1 & 0x00000fc0) >>> 6;
                ++KnLi;
                this.keys[KnLi] = (raw0 & 0x0003f000) << 12;
                this.keys[KnLi] |= (raw0 & 0x0000003f) << 16;
                this.keys[KnLi] |= (raw1 & 0x0003f000) >>> 4;
                this.keys[KnLi] |= (raw1 & 0x0000003f);
                ++KnLi;
            }
        }

        // Encrypt 8 bytes of text
        enc8(text) {
            const b = text.slice();
            let i = 0, l, r, x; // left, right, accumulator

            // Squash 8 bytes to 2 ints
            l = b[i++]<<24 | b[i++]<<16 | b[i++]<<8 | b[i++];
            r = b[i++]<<24 | b[i++]<<16 | b[i++]<<8 | b[i++];

            x = ((l >>> 4) ^ r) & 0x0f0f0f0f;
            r ^= x;
            l ^= (x << 4);
            x = ((l >>> 16) ^ r) & 0x0000ffff;
            r ^= x;
            l ^= (x << 16);
            x = ((r >>> 2) ^ l) & 0x33333333;
            l ^= x;
            r ^= (x << 2);
            x = ((r >>> 8) ^ l) & 0x00ff00ff;
            l ^= x;
            r ^= (x << 8);
            r = (r << 1) | ((r >>> 31) & 1);
            x = (l ^ r) & 0xaaaaaaaa;
            l ^= x;
            r ^= x;
            l = (l << 1) | ((l >>> 31) & 1);

            for (let i = 0, keysi = 0; i < 8; ++i) {
                x = (r << 28) | (r >>> 4);
                x ^= this.keys[keysi++];
                let fval =  $$des$$SP7[x & 0x3f];
                fval |= $$des$$SP5[(x >>> 8) & 0x3f];
                fval |= $$des$$SP3[(x >>> 16) & 0x3f];
                fval |= $$des$$SP1[(x >>> 24) & 0x3f];
                x = r ^ this.keys[keysi++];
                fval |= $$des$$SP8[x & 0x3f];
                fval |= $$des$$SP6[(x >>> 8) & 0x3f];
                fval |= $$des$$SP4[(x >>> 16) & 0x3f];
                fval |= $$des$$SP2[(x >>> 24) & 0x3f];
                l ^= fval;
                x = (l << 28) | (l >>> 4);
                x ^= this.keys[keysi++];
                fval =  $$des$$SP7[x & 0x3f];
                fval |= $$des$$SP5[(x >>> 8) & 0x3f];
                fval |= $$des$$SP3[(x >>> 16) & 0x3f];
                fval |= $$des$$SP1[(x >>> 24) & 0x3f];
                x = l ^ this.keys[keysi++];
                fval |= $$des$$SP8[x & 0x0000003f];
                fval |= $$des$$SP6[(x >>> 8) & 0x3f];
                fval |= $$des$$SP4[(x >>> 16) & 0x3f];
                fval |= $$des$$SP2[(x >>> 24) & 0x3f];
                r ^= fval;
            }

            r = (r << 31) | (r >>> 1);
            x = (l ^ r) & 0xaaaaaaaa;
            l ^= x;
            r ^= x;
            l = (l << 31) | (l >>> 1);
            x = ((l >>> 8) ^ r) & 0x00ff00ff;
            r ^= x;
            l ^= (x << 8);
            x = ((l >>> 2) ^ r) & 0x33333333;
            r ^= x;
            l ^= (x << 2);
            x = ((r >>> 16) ^ l) & 0x0000ffff;
            l ^= x;
            r ^= (x << 16);
            x = ((r >>> 4) ^ l) & 0x0f0f0f0f;
            l ^= x;
            r ^= (x << 4);

            // Spread ints to bytes
            x = [r, l];
            for (i = 0; i < 8; i++) {
                b[i] = (x[i>>>2] >>> (8 * (3 - (i % 4)))) % 256;
                if (b[i] < 0) { b[i] += 256; } // unsigned
            }
            return b;
        }

        // Encrypt 16 bytes of text using passwd as key
        encrypt(t) {
            return this.enc8(t.slice(0, 8)).concat(this.enc8(t.slice(8, 16)));
        }
    }

    var $$des$$default = $$des$$DES;

    var $$input$xtscancodes$$default = {
        "Again": 0xe005,

        /* html:Again (Again) -> linux:129 (KEY_AGAIN) -> atset1:57349 */
        "AltLeft": 0x38,

        /* html:AltLeft (AltLeft) -> linux:56 (KEY_LEFTALT) -> atset1:56 */
        "AltRight": 0xe038,

        /* html:AltRight (AltRight) -> linux:100 (KEY_RIGHTALT) -> atset1:57400 */
        "ArrowDown": 0xe050,

        /* html:ArrowDown (ArrowDown) -> linux:108 (KEY_DOWN) -> atset1:57424 */
        "ArrowLeft": 0xe04b,

        /* html:ArrowLeft (ArrowLeft) -> linux:105 (KEY_LEFT) -> atset1:57419 */
        "ArrowRight": 0xe04d,

        /* html:ArrowRight (ArrowRight) -> linux:106 (KEY_RIGHT) -> atset1:57421 */
        "ArrowUp": 0xe048,

        /* html:ArrowUp (ArrowUp) -> linux:103 (KEY_UP) -> atset1:57416 */
        "AudioVolumeDown": 0xe02e,

        /* html:AudioVolumeDown (AudioVolumeDown) -> linux:114 (KEY_VOLUMEDOWN) -> atset1:57390 */
        "AudioVolumeMute": 0xe020,

        /* html:AudioVolumeMute (AudioVolumeMute) -> linux:113 (KEY_MUTE) -> atset1:57376 */
        "AudioVolumeUp": 0xe030,

        /* html:AudioVolumeUp (AudioVolumeUp) -> linux:115 (KEY_VOLUMEUP) -> atset1:57392 */
        "Backquote": 0x29,

        /* html:Backquote (Backquote) -> linux:41 (KEY_GRAVE) -> atset1:41 */
        "Backslash": 0x2b,

        /* html:Backslash (Backslash) -> linux:43 (KEY_BACKSLASH) -> atset1:43 */
        "Backspace": 0xe,

        /* html:Backspace (Backspace) -> linux:14 (KEY_BACKSPACE) -> atset1:14 */
        "BracketLeft": 0x1a,

        /* html:BracketLeft (BracketLeft) -> linux:26 (KEY_LEFTBRACE) -> atset1:26 */
        "BracketRight": 0x1b,

        /* html:BracketRight (BracketRight) -> linux:27 (KEY_RIGHTBRACE) -> atset1:27 */
        "BrowserBack": 0xe06a,

        /* html:BrowserBack (BrowserBack) -> linux:158 (KEY_BACK) -> atset1:57450 */
        "BrowserFavorites": 0xe066,

        /* html:BrowserFavorites (BrowserFavorites) -> linux:156 (KEY_BOOKMARKS) -> atset1:57446 */
        "BrowserForward": 0xe069,

        /* html:BrowserForward (BrowserForward) -> linux:159 (KEY_FORWARD) -> atset1:57449 */
        "BrowserHome": 0xe032,

        /* html:BrowserHome (BrowserHome) -> linux:172 (KEY_HOMEPAGE) -> atset1:57394 */
        "BrowserRefresh": 0xe067,

        /* html:BrowserRefresh (BrowserRefresh) -> linux:173 (KEY_REFRESH) -> atset1:57447 */
        "BrowserSearch": 0xe065,

        /* html:BrowserSearch (BrowserSearch) -> linux:217 (KEY_SEARCH) -> atset1:57445 */
        "BrowserStop": 0xe068,

        /* html:BrowserStop (BrowserStop) -> linux:128 (KEY_STOP) -> atset1:57448 */
        "CapsLock": 0x3a,

        /* html:CapsLock (CapsLock) -> linux:58 (KEY_CAPSLOCK) -> atset1:58 */
        "Comma": 0x33,

        /* html:Comma (Comma) -> linux:51 (KEY_COMMA) -> atset1:51 */
        "ContextMenu": 0xe05d,

        /* html:ContextMenu (ContextMenu) -> linux:127 (KEY_COMPOSE) -> atset1:57437 */
        "ControlLeft": 0x1d,

        /* html:ControlLeft (ControlLeft) -> linux:29 (KEY_LEFTCTRL) -> atset1:29 */
        "ControlRight": 0xe01d,

        /* html:ControlRight (ControlRight) -> linux:97 (KEY_RIGHTCTRL) -> atset1:57373 */
        "Convert": 0x79,

        /* html:Convert (Convert) -> linux:92 (KEY_HENKAN) -> atset1:121 */
        "Copy": 0xe078,

        /* html:Copy (Copy) -> linux:133 (KEY_COPY) -> atset1:57464 */
        "Cut": 0xe03c,

        /* html:Cut (Cut) -> linux:137 (KEY_CUT) -> atset1:57404 */
        "Delete": 0xe053,

        /* html:Delete (Delete) -> linux:111 (KEY_DELETE) -> atset1:57427 */
        "Digit0": 0xb,

        /* html:Digit0 (Digit0) -> linux:11 (KEY_0) -> atset1:11 */
        "Digit1": 0x2,

        /* html:Digit1 (Digit1) -> linux:2 (KEY_1) -> atset1:2 */
        "Digit2": 0x3,

        /* html:Digit2 (Digit2) -> linux:3 (KEY_2) -> atset1:3 */
        "Digit3": 0x4,

        /* html:Digit3 (Digit3) -> linux:4 (KEY_3) -> atset1:4 */
        "Digit4": 0x5,

        /* html:Digit4 (Digit4) -> linux:5 (KEY_4) -> atset1:5 */
        "Digit5": 0x6,

        /* html:Digit5 (Digit5) -> linux:6 (KEY_5) -> atset1:6 */
        "Digit6": 0x7,

        /* html:Digit6 (Digit6) -> linux:7 (KEY_6) -> atset1:7 */
        "Digit7": 0x8,

        /* html:Digit7 (Digit7) -> linux:8 (KEY_7) -> atset1:8 */
        "Digit8": 0x9,

        /* html:Digit8 (Digit8) -> linux:9 (KEY_8) -> atset1:9 */
        "Digit9": 0xa,

        /* html:Digit9 (Digit9) -> linux:10 (KEY_9) -> atset1:10 */
        "Eject": 0xe07d,

        /* html:Eject (Eject) -> linux:162 (KEY_EJECTCLOSECD) -> atset1:57469 */
        "End": 0xe04f,

        /* html:End (End) -> linux:107 (KEY_END) -> atset1:57423 */
        "Enter": 0x1c,

        /* html:Enter (Enter) -> linux:28 (KEY_ENTER) -> atset1:28 */
        "Equal": 0xd,

        /* html:Equal (Equal) -> linux:13 (KEY_EQUAL) -> atset1:13 */
        "Escape": 0x1,

        /* html:Escape (Escape) -> linux:1 (KEY_ESC) -> atset1:1 */
        "F1": 0x3b,

        /* html:F1 (F1) -> linux:59 (KEY_F1) -> atset1:59 */
        "F10": 0x44,

        /* html:F10 (F10) -> linux:68 (KEY_F10) -> atset1:68 */
        "F11": 0x57,

        /* html:F11 (F11) -> linux:87 (KEY_F11) -> atset1:87 */
        "F12": 0x58,

        /* html:F12 (F12) -> linux:88 (KEY_F12) -> atset1:88 */
        "F13": 0x5d,

        /* html:F13 (F13) -> linux:183 (KEY_F13) -> atset1:93 */
        "F14": 0x5e,

        /* html:F14 (F14) -> linux:184 (KEY_F14) -> atset1:94 */
        "F15": 0x5f,

        /* html:F15 (F15) -> linux:185 (KEY_F15) -> atset1:95 */
        "F16": 0x55,

        /* html:F16 (F16) -> linux:186 (KEY_F16) -> atset1:85 */
        "F17": 0xe003,

        /* html:F17 (F17) -> linux:187 (KEY_F17) -> atset1:57347 */
        "F18": 0xe077,

        /* html:F18 (F18) -> linux:188 (KEY_F18) -> atset1:57463 */
        "F19": 0xe004,

        /* html:F19 (F19) -> linux:189 (KEY_F19) -> atset1:57348 */
        "F2": 0x3c,

        /* html:F2 (F2) -> linux:60 (KEY_F2) -> atset1:60 */
        "F20": 0x5a,

        /* html:F20 (F20) -> linux:190 (KEY_F20) -> atset1:90 */
        "F21": 0x74,

        /* html:F21 (F21) -> linux:191 (KEY_F21) -> atset1:116 */
        "F22": 0xe079,

        /* html:F22 (F22) -> linux:192 (KEY_F22) -> atset1:57465 */
        "F23": 0x6d,

        /* html:F23 (F23) -> linux:193 (KEY_F23) -> atset1:109 */
        "F24": 0x6f,

        /* html:F24 (F24) -> linux:194 (KEY_F24) -> atset1:111 */
        "F3": 0x3d,

        /* html:F3 (F3) -> linux:61 (KEY_F3) -> atset1:61 */
        "F4": 0x3e,

        /* html:F4 (F4) -> linux:62 (KEY_F4) -> atset1:62 */
        "F5": 0x3f,

        /* html:F5 (F5) -> linux:63 (KEY_F5) -> atset1:63 */
        "F6": 0x40,

        /* html:F6 (F6) -> linux:64 (KEY_F6) -> atset1:64 */
        "F7": 0x41,

        /* html:F7 (F7) -> linux:65 (KEY_F7) -> atset1:65 */
        "F8": 0x42,

        /* html:F8 (F8) -> linux:66 (KEY_F8) -> atset1:66 */
        "F9": 0x43,

        /* html:F9 (F9) -> linux:67 (KEY_F9) -> atset1:67 */
        "Find": 0xe041,

        /* html:Find (Find) -> linux:136 (KEY_FIND) -> atset1:57409 */
        "Help": 0xe075,

        /* html:Help (Help) -> linux:138 (KEY_HELP) -> atset1:57461 */
        "Hiragana": 0x77,

        /* html:Hiragana (Lang4) -> linux:91 (KEY_HIRAGANA) -> atset1:119 */
        "Home": 0xe047,

        /* html:Home (Home) -> linux:102 (KEY_HOME) -> atset1:57415 */
        "Insert": 0xe052,

        /* html:Insert (Insert) -> linux:110 (KEY_INSERT) -> atset1:57426 */
        "IntlBackslash": 0x56,

        /* html:IntlBackslash (IntlBackslash) -> linux:86 (KEY_102ND) -> atset1:86 */
        "IntlRo": 0x73,

        /* html:IntlRo (IntlRo) -> linux:89 (KEY_RO) -> atset1:115 */
        "IntlYen": 0x7d,

        /* html:IntlYen (IntlYen) -> linux:124 (KEY_YEN) -> atset1:125 */
        "KanaMode": 0x70,

        /* html:KanaMode (KanaMode) -> linux:93 (KEY_KATAKANAHIRAGANA) -> atset1:112 */
        "Katakana": 0x78,

        /* html:Katakana (Lang3) -> linux:90 (KEY_KATAKANA) -> atset1:120 */
        "KeyA": 0x1e,

        /* html:KeyA (KeyA) -> linux:30 (KEY_A) -> atset1:30 */
        "KeyB": 0x30,

        /* html:KeyB (KeyB) -> linux:48 (KEY_B) -> atset1:48 */
        "KeyC": 0x2e,

        /* html:KeyC (KeyC) -> linux:46 (KEY_C) -> atset1:46 */
        "KeyD": 0x20,

        /* html:KeyD (KeyD) -> linux:32 (KEY_D) -> atset1:32 */
        "KeyE": 0x12,

        /* html:KeyE (KeyE) -> linux:18 (KEY_E) -> atset1:18 */
        "KeyF": 0x21,

        /* html:KeyF (KeyF) -> linux:33 (KEY_F) -> atset1:33 */
        "KeyG": 0x22,

        /* html:KeyG (KeyG) -> linux:34 (KEY_G) -> atset1:34 */
        "KeyH": 0x23,

        /* html:KeyH (KeyH) -> linux:35 (KEY_H) -> atset1:35 */
        "KeyI": 0x17,

        /* html:KeyI (KeyI) -> linux:23 (KEY_I) -> atset1:23 */
        "KeyJ": 0x24,

        /* html:KeyJ (KeyJ) -> linux:36 (KEY_J) -> atset1:36 */
        "KeyK": 0x25,

        /* html:KeyK (KeyK) -> linux:37 (KEY_K) -> atset1:37 */
        "KeyL": 0x26,

        /* html:KeyL (KeyL) -> linux:38 (KEY_L) -> atset1:38 */
        "KeyM": 0x32,

        /* html:KeyM (KeyM) -> linux:50 (KEY_M) -> atset1:50 */
        "KeyN": 0x31,

        /* html:KeyN (KeyN) -> linux:49 (KEY_N) -> atset1:49 */
        "KeyO": 0x18,

        /* html:KeyO (KeyO) -> linux:24 (KEY_O) -> atset1:24 */
        "KeyP": 0x19,

        /* html:KeyP (KeyP) -> linux:25 (KEY_P) -> atset1:25 */
        "KeyQ": 0x10,

        /* html:KeyQ (KeyQ) -> linux:16 (KEY_Q) -> atset1:16 */
        "KeyR": 0x13,

        /* html:KeyR (KeyR) -> linux:19 (KEY_R) -> atset1:19 */
        "KeyS": 0x1f,

        /* html:KeyS (KeyS) -> linux:31 (KEY_S) -> atset1:31 */
        "KeyT": 0x14,

        /* html:KeyT (KeyT) -> linux:20 (KEY_T) -> atset1:20 */
        "KeyU": 0x16,

        /* html:KeyU (KeyU) -> linux:22 (KEY_U) -> atset1:22 */
        "KeyV": 0x2f,

        /* html:KeyV (KeyV) -> linux:47 (KEY_V) -> atset1:47 */
        "KeyW": 0x11,

        /* html:KeyW (KeyW) -> linux:17 (KEY_W) -> atset1:17 */
        "KeyX": 0x2d,

        /* html:KeyX (KeyX) -> linux:45 (KEY_X) -> atset1:45 */
        "KeyY": 0x15,

        /* html:KeyY (KeyY) -> linux:21 (KEY_Y) -> atset1:21 */
        "KeyZ": 0x2c,

        /* html:KeyZ (KeyZ) -> linux:44 (KEY_Z) -> atset1:44 */
        "Lang3": 0x78,

        /* html:Lang3 (Lang3) -> linux:90 (KEY_KATAKANA) -> atset1:120 */
        "Lang4": 0x77,

        /* html:Lang4 (Lang4) -> linux:91 (KEY_HIRAGANA) -> atset1:119 */
        "Lang5": 0x76,

        /* html:Lang5 (Lang5) -> linux:85 (KEY_ZENKAKUHANKAKU) -> atset1:118 */
        "LaunchApp1": 0xe06b,

        /* html:LaunchApp1 (LaunchApp1) -> linux:157 (KEY_COMPUTER) -> atset1:57451 */
        "LaunchApp2": 0xe021,

        /* html:LaunchApp2 (LaunchApp2) -> linux:140 (KEY_CALC) -> atset1:57377 */
        "LaunchMail": 0xe06c,

        /* html:LaunchMail (LaunchMail) -> linux:155 (KEY_MAIL) -> atset1:57452 */
        "MediaPlayPause": 0xe022,

        /* html:MediaPlayPause (MediaPlayPause) -> linux:164 (KEY_PLAYPAUSE) -> atset1:57378 */
        "MediaSelect": 0xe06d,

        /* html:MediaSelect (MediaSelect) -> linux:226 (KEY_MEDIA) -> atset1:57453 */
        "MediaStop": 0xe024,

        /* html:MediaStop (MediaStop) -> linux:166 (KEY_STOPCD) -> atset1:57380 */
        "MediaTrackNext": 0xe019,

        /* html:MediaTrackNext (MediaTrackNext) -> linux:163 (KEY_NEXTSONG) -> atset1:57369 */
        "MediaTrackPrevious": 0xe010,

        /* html:MediaTrackPrevious (MediaTrackPrevious) -> linux:165 (KEY_PREVIOUSSONG) -> atset1:57360 */
        "MetaLeft": 0xe05b,

        /* html:MetaLeft (MetaLeft) -> linux:125 (KEY_LEFTMETA) -> atset1:57435 */
        "MetaRight": 0xe05c,

        /* html:MetaRight (MetaRight) -> linux:126 (KEY_RIGHTMETA) -> atset1:57436 */
        "Minus": 0xc,

        /* html:Minus (Minus) -> linux:12 (KEY_MINUS) -> atset1:12 */
        "NonConvert": 0x7b,

        /* html:NonConvert (NonConvert) -> linux:94 (KEY_MUHENKAN) -> atset1:123 */
        "NumLock": 0x45,

        /* html:NumLock (NumLock) -> linux:69 (KEY_NUMLOCK) -> atset1:69 */
        "Numpad0": 0x52,

        /* html:Numpad0 (Numpad0) -> linux:82 (KEY_KP0) -> atset1:82 */
        "Numpad1": 0x4f,

        /* html:Numpad1 (Numpad1) -> linux:79 (KEY_KP1) -> atset1:79 */
        "Numpad2": 0x50,

        /* html:Numpad2 (Numpad2) -> linux:80 (KEY_KP2) -> atset1:80 */
        "Numpad3": 0x51,

        /* html:Numpad3 (Numpad3) -> linux:81 (KEY_KP3) -> atset1:81 */
        "Numpad4": 0x4b,

        /* html:Numpad4 (Numpad4) -> linux:75 (KEY_KP4) -> atset1:75 */
        "Numpad5": 0x4c,

        /* html:Numpad5 (Numpad5) -> linux:76 (KEY_KP5) -> atset1:76 */
        "Numpad6": 0x4d,

        /* html:Numpad6 (Numpad6) -> linux:77 (KEY_KP6) -> atset1:77 */
        "Numpad7": 0x47,

        /* html:Numpad7 (Numpad7) -> linux:71 (KEY_KP7) -> atset1:71 */
        "Numpad8": 0x48,

        /* html:Numpad8 (Numpad8) -> linux:72 (KEY_KP8) -> atset1:72 */
        "Numpad9": 0x49,

        /* html:Numpad9 (Numpad9) -> linux:73 (KEY_KP9) -> atset1:73 */
        "NumpadAdd": 0x4e,

        /* html:NumpadAdd (NumpadAdd) -> linux:78 (KEY_KPPLUS) -> atset1:78 */
        "NumpadComma": 0x7e,

        /* html:NumpadComma (NumpadComma) -> linux:121 (KEY_KPCOMMA) -> atset1:126 */
        "NumpadDecimal": 0x53,

        /* html:NumpadDecimal (NumpadDecimal) -> linux:83 (KEY_KPDOT) -> atset1:83 */
        "NumpadDivide": 0xe035,

        /* html:NumpadDivide (NumpadDivide) -> linux:98 (KEY_KPSLASH) -> atset1:57397 */
        "NumpadEnter": 0xe01c,

        /* html:NumpadEnter (NumpadEnter) -> linux:96 (KEY_KPENTER) -> atset1:57372 */
        "NumpadEqual": 0x59,

        /* html:NumpadEqual (NumpadEqual) -> linux:117 (KEY_KPEQUAL) -> atset1:89 */
        "NumpadMultiply": 0x37,

        /* html:NumpadMultiply (NumpadMultiply) -> linux:55 (KEY_KPASTERISK) -> atset1:55 */
        "NumpadParenLeft": 0xe076,

        /* html:NumpadParenLeft (NumpadParenLeft) -> linux:179 (KEY_KPLEFTPAREN) -> atset1:57462 */
        "NumpadParenRight": 0xe07b,

        /* html:NumpadParenRight (NumpadParenRight) -> linux:180 (KEY_KPRIGHTPAREN) -> atset1:57467 */
        "NumpadSubtract": 0x4a,

        /* html:NumpadSubtract (NumpadSubtract) -> linux:74 (KEY_KPMINUS) -> atset1:74 */
        "Open": 0x64,

        /* html:Open (Open) -> linux:134 (KEY_OPEN) -> atset1:100 */
        "PageDown": 0xe051,

        /* html:PageDown (PageDown) -> linux:109 (KEY_PAGEDOWN) -> atset1:57425 */
        "PageUp": 0xe049,

        /* html:PageUp (PageUp) -> linux:104 (KEY_PAGEUP) -> atset1:57417 */
        "Paste": 0x65,

        /* html:Paste (Paste) -> linux:135 (KEY_PASTE) -> atset1:101 */
        "Pause": 0xe046,

        /* html:Pause (Pause) -> linux:119 (KEY_PAUSE) -> atset1:57414 */
        "Period": 0x34,

        /* html:Period (Period) -> linux:52 (KEY_DOT) -> atset1:52 */
        "Power": 0xe05e,

        /* html:Power (Power) -> linux:116 (KEY_POWER) -> atset1:57438 */
        "PrintScreen": 0x54,

        /* html:PrintScreen (PrintScreen) -> linux:99 (KEY_SYSRQ) -> atset1:84 */
        "Props": 0xe006,

        /* html:Props (Props) -> linux:130 (KEY_PROPS) -> atset1:57350 */
        "Quote": 0x28,

        /* html:Quote (Quote) -> linux:40 (KEY_APOSTROPHE) -> atset1:40 */
        "ScrollLock": 0x46,

        /* html:ScrollLock (ScrollLock) -> linux:70 (KEY_SCROLLLOCK) -> atset1:70 */
        "Semicolon": 0x27,

        /* html:Semicolon (Semicolon) -> linux:39 (KEY_SEMICOLON) -> atset1:39 */
        "ShiftLeft": 0x2a,

        /* html:ShiftLeft (ShiftLeft) -> linux:42 (KEY_LEFTSHIFT) -> atset1:42 */
        "ShiftRight": 0x36,

        /* html:ShiftRight (ShiftRight) -> linux:54 (KEY_RIGHTSHIFT) -> atset1:54 */
        "Slash": 0x35,

        /* html:Slash (Slash) -> linux:53 (KEY_SLASH) -> atset1:53 */
        "Sleep": 0xe05f,

        /* html:Sleep (Sleep) -> linux:142 (KEY_SLEEP) -> atset1:57439 */
        "Space": 0x39,

        /* html:Space (Space) -> linux:57 (KEY_SPACE) -> atset1:57 */
        "Suspend": 0xe025,

        /* html:Suspend (Suspend) -> linux:205 (KEY_SUSPEND) -> atset1:57381 */
        "Tab": 0xf,

        /* html:Tab (Tab) -> linux:15 (KEY_TAB) -> atset1:15 */
        "Undo": 0xe007,

        /* html:Undo (Undo) -> linux:131 (KEY_UNDO) -> atset1:57351 */
        "WakeUp": 0xe063 /* html:WakeUp (WakeUp) -> linux:143 (KEY_WAKEUP) -> atset1:57443 */
    };

    const $$encodings$$encodings = {
        encodingRaw: 0,
        encodingCopyRect: 1,
        encodingRRE: 2,
        encodingHextile: 5,
        encodingTight: 7,
        encodingTightPNG: -260,

        pseudoEncodingQualityLevel9: -23,
        pseudoEncodingQualityLevel0: -32,
        pseudoEncodingDesktopSize: -223,
        pseudoEncodingLastRect: -224,
        pseudoEncodingCursor: -239,
        pseudoEncodingQEMUExtendedKeyEvent: -258,
        pseudoEncodingExtendedDesktopSize: -308,
        pseudoEncodingXvp: -309,
        pseudoEncodingFence: -312,
        pseudoEncodingContinuousUpdates: -313,
        pseudoEncodingCompressLevel9: -247,
        pseudoEncodingCompressLevel0: -256,
    };

    function $$encodings$$encodingName(num) {
        switch (num) {
            case $$encodings$$encodings.encodingRaw:      return "Raw";
            case $$encodings$$encodings.encodingCopyRect: return "CopyRect";
            case $$encodings$$encodings.encodingRRE:      return "RRE";
            case $$encodings$$encodings.encodingHextile:  return "Hextile";
            case $$encodings$$encodings.encodingTight:    return "Tight";
            case $$encodings$$encodings.encodingTightPNG: return "TightPNG";
            default:                         return "[unknown encoding " + num + "]";
        }
    }

    /*
     * noVNC: HTML5 VNC client
     * Copyright (C) 2018 The noVNC Authors
     * Licensed under MPL 2.0 or any later version (see LICENSE.txt)
     */

    /* Polyfills to provide new APIs in old browsers */

    /* Object.assign() (taken from MDN) */
    if (typeof Object.assign != 'function') {
        // Must be writable: true, enumerable: false, configurable: true
        Object.defineProperty(Object, "assign", {
            value: function assign(target, varArgs) { // .length of function is 2
                'use strict';
                if (target == null) { // TypeError if undefined or null
                    throw new TypeError('Cannot convert undefined or null to object');
                }

                const to = Object(target);

                for (let index = 1; index < arguments.length; index++) {
                    const nextSource = arguments[index];

                    if (nextSource != null) { // Skip over if undefined or null
                        for (let nextKey in nextSource) {
                            // Avoid bugs when hasOwnProperty is shadowed
                            if (Object.prototype.hasOwnProperty.call(nextSource, nextKey)) {
                                to[nextKey] = nextSource[nextKey];
                            }
                        }
                    }
                }
                return to;
            },
            writable: true,
            configurable: true
        });
    }

    /* CustomEvent constructor (taken from MDN) */
    (() => {
        function CustomEvent(event, params) {
            params = params || { bubbles: false, cancelable: false, detail: undefined };
            const evt = document.createEvent( 'CustomEvent' );
            evt.initCustomEvent( event, params.bubbles, params.cancelable, params.detail );
            return evt;
        }

        CustomEvent.prototype = window.Event.prototype;

        if (typeof window.CustomEvent !== "function") {
            window.CustomEvent = CustomEvent;
        }
    })();

    class $$decoders$raw$$RawDecoder {
        constructor() {
            this._lines = 0;
        }

        decodeRect(x, y, width, height, sock, display, depth) {
            if (this._lines === 0) {
                this._lines = height;
            }

            const pixelSize = depth == 8 ? 1 : 4;
            const bytesPerLine = width * pixelSize;

            if (sock.rQwait("RAW", bytesPerLine)) {
                return false;
            }

            const cur_y = y + (height - this._lines);
            const curr_height = Math.min(this._lines,
                                         Math.floor(sock.rQlen / bytesPerLine));
            let data = sock.rQ;
            let index = sock.rQi;

            // Convert data if needed
            if (depth == 8) {
                const pixels = width * curr_height;
                const newdata = new Uint8Array(pixels * 4);
                for (let i = 0; i < pixels; i++) {
                    newdata[i * 4 + 0] = ((data[index + i] >> 0) & 0x3) * 255 / 3;
                    newdata[i * 4 + 1] = ((data[index + i] >> 2) & 0x3) * 255 / 3;
                    newdata[i * 4 + 2] = ((data[index + i] >> 4) & 0x3) * 255 / 3;
                    newdata[i * 4 + 4] = 0;
                }
                data = newdata;
                index = 0;
            }

            display.blitImage(x, cur_y, width, curr_height, data, index);
            sock.rQskipBytes(curr_height * bytesPerLine);
            this._lines -= curr_height;
            if (this._lines > 0) {
                return false;
            }

            return true;
        }
    }

    var $$decoders$raw$$default = $$decoders$raw$$RawDecoder;

    class $$decoders$copyrect$$CopyRectDecoder {
        decodeRect(x, y, width, height, sock, display, depth) {
            if (sock.rQwait("COPYRECT", 4)) {
                return false;
            }

            let deltaX = sock.rQshift16();
            let deltaY = sock.rQshift16();
            display.copyImage(deltaX, deltaY, x, y, width, height);

            return true;
        }
    }

    var $$decoders$copyrect$$default = $$decoders$copyrect$$CopyRectDecoder;

    class $$decoders$rre$$RREDecoder {
        constructor() {
            this._subrects = 0;
        }

        decodeRect(x, y, width, height, sock, display, depth) {
            if (this._subrects === 0) {
                if (sock.rQwait("RRE", 4 + 4)) {
                    return false;
                }

                this._subrects = sock.rQshift32();

                let color = sock.rQshiftBytes(4);  // Background
                display.fillRect(x, y, width, height, color);
            }

            while (this._subrects > 0) {
                if (sock.rQwait("RRE", 4 + 8)) {
                    return false;
                }

                let color = sock.rQshiftBytes(4);
                let sx = sock.rQshift16();
                let sy = sock.rQshift16();
                let swidth = sock.rQshift16();
                let sheight = sock.rQshift16();
                display.fillRect(x + sx, y + sy, swidth, sheight, color);

                this._subrects--;
            }

            return true;
        }
    }

    var $$decoders$rre$$default = $$decoders$rre$$RREDecoder;

    class $$decoders$hextile$$HextileDecoder {
        constructor() {
            this._tiles = 0;
            this._lastsubencoding = 0;
        }

        decodeRect(x, y, width, height, sock, display, depth) {
            if (this._tiles === 0) {
                this._tiles_x = Math.ceil(width / 16);
                this._tiles_y = Math.ceil(height / 16);
                this._total_tiles = this._tiles_x * this._tiles_y;
                this._tiles = this._total_tiles;
            }

            while (this._tiles > 0) {
                let bytes = 1;

                if (sock.rQwait("HEXTILE", bytes)) {
                    return false;
                }

                let rQ = sock.rQ;
                let rQi = sock.rQi;

                let subencoding = rQ[rQi];  // Peek
                if (subencoding > 30) {  // Raw
                    throw new Error("Illegal hextile subencoding (subencoding: " +
                                subencoding + ")");
                }

                const curr_tile = this._total_tiles - this._tiles;
                const tile_x = curr_tile % this._tiles_x;
                const tile_y = Math.floor(curr_tile / this._tiles_x);
                const tx = x + tile_x * 16;
                const ty = y + tile_y * 16;
                const tw = Math.min(16, (x + width) - tx);
                const th = Math.min(16, (y + height) - ty);

                // Figure out how much we are expecting
                if (subencoding & 0x01) {  // Raw
                    bytes += tw * th * 4;
                } else {
                    if (subencoding & 0x02) {  // Background
                        bytes += 4;
                    }
                    if (subencoding & 0x04) {  // Foreground
                        bytes += 4;
                    }
                    if (subencoding & 0x08) {  // AnySubrects
                        bytes++;  // Since we aren't shifting it off

                        if (sock.rQwait("HEXTILE", bytes)) {
                            return false;
                        }

                        let subrects = rQ[rQi + bytes - 1];  // Peek
                        if (subencoding & 0x10) {  // SubrectsColoured
                            bytes += subrects * (4 + 2);
                        } else {
                            bytes += subrects * 2;
                        }
                    }
                }

                if (sock.rQwait("HEXTILE", bytes)) {
                    return false;
                }

                // We know the encoding and have a whole tile
                rQi++;
                if (subencoding === 0) {
                    if (this._lastsubencoding & 0x01) {
                        // Weird: ignore blanks are RAW
                        $$$core$util$logging$$.Debug("     Ignoring blank after RAW");
                    } else {
                        display.fillRect(tx, ty, tw, th, this._background);
                    }
                } else if (subencoding & 0x01) {  // Raw
                    display.blitImage(tx, ty, tw, th, rQ, rQi);
                    rQi += bytes - 1;
                } else {
                    if (subencoding & 0x02) {  // Background
                        this._background = [rQ[rQi], rQ[rQi + 1], rQ[rQi + 2], rQ[rQi + 3]];
                        rQi += 4;
                    }
                    if (subencoding & 0x04) {  // Foreground
                        this._foreground = [rQ[rQi], rQ[rQi + 1], rQ[rQi + 2], rQ[rQi + 3]];
                        rQi += 4;
                    }

                    display.startTile(tx, ty, tw, th, this._background);
                    if (subencoding & 0x08) {  // AnySubrects
                        let subrects = rQ[rQi];
                        rQi++;

                        for (let s = 0; s < subrects; s++) {
                            let color;
                            if (subencoding & 0x10) {  // SubrectsColoured
                                color = [rQ[rQi], rQ[rQi + 1], rQ[rQi + 2], rQ[rQi + 3]];
                                rQi += 4;
                            } else {
                                color = this._foreground;
                            }
                            const xy = rQ[rQi];
                            rQi++;
                            const sx = (xy >> 4);
                            const sy = (xy & 0x0f);

                            const wh = rQ[rQi];
                            rQi++;
                            const sw = (wh >> 4) + 1;
                            const sh = (wh & 0x0f) + 1;

                            display.subTile(sx, sy, sw, sh, color);
                        }
                    }
                    display.finishTile();
                }
                sock.rQi = rQi;
                this._lastsubencoding = subencoding;
                this._tiles--;
            }

            return true;
        }
    }

    var $$decoders$hextile$$default = $$decoders$hextile$$HextileDecoder;

    function $$$utils$common$$shrinkBuf(buf, size) {
      if (buf.length === size) { return buf; }
      if (buf.subarray) { return buf.subarray(0, size); }
      buf.length = size;
      return buf;
    }

    function $$$utils$common$$arraySet(dest, src, src_offs, len, dest_offs) {
      if (src.subarray && dest.subarray) {
        dest.set(src.subarray(src_offs, src_offs + len), dest_offs);
        return;
      }
      // Fallback to ordinary array
      for (var i = 0; i < len; i++) {
        dest[dest_offs + i] = src[src_offs + i];
      }
    }

    function $$$utils$common$$flattenChunks(chunks) {
      var i, l, len, pos, chunk, result;

      // calculate data length
      len = 0;
      for (i = 0, l = chunks.length; i < l; i++) {
        len += chunks[i].length;
      }

      // join chunks
      result = new Uint8Array(len);
      pos = 0;
      for (i = 0, l = chunks.length; i < l; i++) {
        chunk = chunks[i];
        result.set(chunk, pos);
        pos += chunk.length;
      }

      return result;
    }

    var $$$utils$common$$Buf8  = Uint8Array;
    var $$$utils$common$$Buf16 = Uint16Array;
    var $$$utils$common$$Buf32 = Int32Array;

    function $$adler32$$adler32(adler, buf, len, pos) {
      var s1 = (adler & 0xffff) |0,
          s2 = ((adler >>> 16) & 0xffff) |0,
          n = 0;

      while (len !== 0) {
        // Set limit ~ twice less than 5552, to keep
        // s2 in 31-bits, because we force signed ints.
        // in other case %= will fail.
        n = len > 2000 ? 2000 : len;
        len -= n;

        do {
          s1 = (s1 + buf[pos++]) |0;
          s2 = (s2 + s1) |0;
        } while (--n);

        s1 %= 65521;
        s2 %= 65521;
      }

      return (s1 | (s2 << 16)) |0;
    }

    var $$adler32$$default = $$adler32$$adler32;

    function $$crc32$$makeTable() {
      var c, table = [];

      for (var n = 0; n < 256; n++) {
        c = n;
        for (var k = 0; k < 8; k++) {
          c = ((c & 1) ? (0xEDB88320 ^ (c >>> 1)) : (c >>> 1));
        }
        table[n] = c;
      }

      return table;
    }

    var $$crc32$$default = $$crc32$$makeTable;

    // Create table on load. Just 255 signed longs. Not a problem.
    var $$crc32$$crcTable = $$crc32$$makeTable();


    function $$crc32$$crc32(crc, buf, len, pos) {
      var t = $$crc32$$crcTable,
          end = pos + len;

      crc ^= -1;

      for (var i = pos; i < end; i++) {
        crc = (crc >>> 8) ^ t[(crc ^ buf[i]) & 0xFF];
      }

      return (crc ^ (-1)); // >>> 0;
    }
    // See state defs from inflate.js
    var $$inffast$$BAD = 30;/* got a data error -- remain here until reset */
    var $$inffast$$TYPE = 12;

    function $$inffast$$inflate_fast(strm, start) {
      var state;
      var _in;                    /* local strm.input */
      var last;                   /* have enough input while in < last */
      var _out;                   /* local strm.output */
      var beg;                    /* inflate()'s initial strm.output */
      var end;                    /* while out < end, enough space available */
    //#ifdef INFLATE_STRICT
      var dmax;                   /* maximum distance from zlib header */
    //#endif
      var wsize;                  /* window size or zero if not using window */
      var whave;                  /* valid bytes in the window */
      var wnext;                  /* window write index */
      // Use `s_window` instead `window`, avoid conflict with instrumentation tools
      var s_window;               /* allocated sliding window, if wsize != 0 */
      var hold;                   /* local strm.hold */
      var bits;                   /* local strm.bits */
      var lcode;                  /* local strm.lencode */
      var dcode;                  /* local strm.distcode */
      var lmask;                  /* mask for first level of length codes */
      var dmask;                  /* mask for first level of distance codes */
      var here;                   /* retrieved table entry */
      var op;                     /* code bits, operation, extra bits, or */
                                  /*  window position, window bytes to copy */
      var len;                    /* match length, unused bytes */
      var dist;                   /* match distance */
      var from;                   /* where to copy match from */
      var from_source;


      var input, output; // JS specific, because we have no pointers

      /* copy state to local variables */
      state = strm.state;
      //here = state.here;
      _in = strm.next_in;
      input = strm.input;
      last = _in + (strm.avail_in - 5);
      _out = strm.next_out;
      output = strm.output;
      beg = _out - (start - strm.avail_out);
      end = _out + (strm.avail_out - 257);
    //#ifdef INFLATE_STRICT
      dmax = state.dmax;
    //#endif
      wsize = state.wsize;
      whave = state.whave;
      wnext = state.wnext;
      s_window = state.window;
      hold = state.hold;
      bits = state.bits;
      lcode = state.lencode;
      dcode = state.distcode;
      lmask = (1 << state.lenbits) - 1;
      dmask = (1 << state.distbits) - 1;


      /* decode literals and length/distances until end-of-block or not enough
         input data or output space */

      top:
      do {
        if (bits < 15) {
          hold += input[_in++] << bits;
          bits += 8;
          hold += input[_in++] << bits;
          bits += 8;
        }

        here = lcode[hold & lmask];

        dolen:
        for (;;) { // Goto emulation
          op = here >>> 24/*here.bits*/;
          hold >>>= op;
          bits -= op;
          op = (here >>> 16) & 0xff/*here.op*/;
          if (op === 0) {                          /* literal */
            //Tracevv((stderr, here.val >= 0x20 && here.val < 0x7f ?
            //        "inflate:         literal '%c'\n" :
            //        "inflate:         literal 0x%02x\n", here.val));
            output[_out++] = here & 0xffff/*here.val*/;
          }
          else if (op & 16) {                     /* length base */
            len = here & 0xffff/*here.val*/;
            op &= 15;                           /* number of extra bits */
            if (op) {
              if (bits < op) {
                hold += input[_in++] << bits;
                bits += 8;
              }
              len += hold & ((1 << op) - 1);
              hold >>>= op;
              bits -= op;
            }
            //Tracevv((stderr, "inflate:         length %u\n", len));
            if (bits < 15) {
              hold += input[_in++] << bits;
              bits += 8;
              hold += input[_in++] << bits;
              bits += 8;
            }
            here = dcode[hold & dmask];

            dodist:
            for (;;) { // goto emulation
              op = here >>> 24/*here.bits*/;
              hold >>>= op;
              bits -= op;
              op = (here >>> 16) & 0xff/*here.op*/;

              if (op & 16) {                      /* distance base */
                dist = here & 0xffff/*here.val*/;
                op &= 15;                       /* number of extra bits */
                if (bits < op) {
                  hold += input[_in++] << bits;
                  bits += 8;
                  if (bits < op) {
                    hold += input[_in++] << bits;
                    bits += 8;
                  }
                }
                dist += hold & ((1 << op) - 1);
    //#ifdef INFLATE_STRICT
                if (dist > dmax) {
                  strm.msg = 'invalid distance too far back';
                  state.mode = $$inffast$$BAD;
                  break top;
                }
    //#endif
                hold >>>= op;
                bits -= op;
                //Tracevv((stderr, "inflate:         distance %u\n", dist));
                op = _out - beg;                /* max distance in output */
                if (dist > op) {                /* see if copy from window */
                  op = dist - op;               /* distance back in window */
                  if (op > whave) {
                    if (state.sane) {
                      strm.msg = 'invalid distance too far back';
                      state.mode = $$inffast$$BAD;
                      break top;
                    }

    // (!) This block is disabled in zlib defailts,
    // don't enable it for binary compatibility
    //#ifdef INFLATE_ALLOW_INVALID_DISTANCE_TOOFAR_ARRR
    //                if (len <= op - whave) {
    //                  do {
    //                    output[_out++] = 0;
    //                  } while (--len);
    //                  continue top;
    //                }
    //                len -= op - whave;
    //                do {
    //                  output[_out++] = 0;
    //                } while (--op > whave);
    //                if (op === 0) {
    //                  from = _out - dist;
    //                  do {
    //                    output[_out++] = output[from++];
    //                  } while (--len);
    //                  continue top;
    //                }
    //#endif
                  }
                  from = 0; // window index
                  from_source = s_window;
                  if (wnext === 0) {           /* very common case */
                    from += wsize - op;
                    if (op < len) {         /* some from window */
                      len -= op;
                      do {
                        output[_out++] = s_window[from++];
                      } while (--op);
                      from = _out - dist;  /* rest from output */
                      from_source = output;
                    }
                  }
                  else if (wnext < op) {      /* wrap around window */
                    from += wsize + wnext - op;
                    op -= wnext;
                    if (op < len) {         /* some from end of window */
                      len -= op;
                      do {
                        output[_out++] = s_window[from++];
                      } while (--op);
                      from = 0;
                      if (wnext < len) {  /* some from start of window */
                        op = wnext;
                        len -= op;
                        do {
                          output[_out++] = s_window[from++];
                        } while (--op);
                        from = _out - dist;      /* rest from output */
                        from_source = output;
                      }
                    }
                  }
                  else {                      /* contiguous in window */
                    from += wnext - op;
                    if (op < len) {         /* some from window */
                      len -= op;
                      do {
                        output[_out++] = s_window[from++];
                      } while (--op);
                      from = _out - dist;  /* rest from output */
                      from_source = output;
                    }
                  }
                  while (len > 2) {
                    output[_out++] = from_source[from++];
                    output[_out++] = from_source[from++];
                    output[_out++] = from_source[from++];
                    len -= 3;
                  }
                  if (len) {
                    output[_out++] = from_source[from++];
                    if (len > 1) {
                      output[_out++] = from_source[from++];
                    }
                  }
                }
                else {
                  from = _out - dist;          /* copy direct from output */
                  do {                        /* minimum length is three */
                    output[_out++] = output[from++];
                    output[_out++] = output[from++];
                    output[_out++] = output[from++];
                    len -= 3;
                  } while (len > 2);
                  if (len) {
                    output[_out++] = output[from++];
                    if (len > 1) {
                      output[_out++] = output[from++];
                    }
                  }
                }
              }
              else if ((op & 64) === 0) {          /* 2nd level distance code */
                here = dcode[(here & 0xffff)/*here.val*/ + (hold & ((1 << op) - 1))];
                continue dodist;
              }
              else {
                strm.msg = 'invalid distance code';
                state.mode = $$inffast$$BAD;
                break top;
              }

              break; // need to emulate goto via "continue"
            }
          }
          else if ((op & 64) === 0) {              /* 2nd level length code */
            here = lcode[(here & 0xffff)/*here.val*/ + (hold & ((1 << op) - 1))];
            continue dolen;
          }
          else if (op & 32) {                     /* end-of-block */
            //Tracevv((stderr, "inflate:         end of block\n"));
            state.mode = $$inffast$$TYPE;
            break top;
          }
          else {
            strm.msg = 'invalid literal/length code';
            state.mode = $$inffast$$BAD;
            break top;
          }

          break; // need to emulate goto via "continue"
        }
      } while (_in < last && _out < end);

      /* return unused bytes (on entry, bits < 8, so in won't go too far back) */
      len = bits >> 3;
      _in -= len;
      bits -= len << 3;
      hold &= (1 << bits) - 1;

      /* update state and return */
      strm.next_in = _in;
      strm.next_out = _out;
      strm.avail_in = (_in < last ? 5 + (last - _in) : 5 - (_in - last));
      strm.avail_out = (_out < end ? 257 + (end - _out) : 257 - (_out - end));
      state.hold = hold;
      state.bits = bits;
      return;
    }

    var $$inffast$$default = $$inffast$$inflate_fast;

    var $$inftrees$$MAXBITS = 15;
    var $$inftrees$$ENOUGH_LENS = 852;
    var $$inftrees$$ENOUGH_DISTS = 592;
    //var ENOUGH = (ENOUGH_LENS+ENOUGH_DISTS);

    var $$inftrees$$CODES = 0;
    var $$inftrees$$LENS = 1;
    var $$inftrees$$DISTS = 2;

    var $$inftrees$$lbase = [ /* Length codes 257..285 base */
      3, 4, 5, 6, 7, 8, 9, 10, 11, 13, 15, 17, 19, 23, 27, 31,
      35, 43, 51, 59, 67, 83, 99, 115, 131, 163, 195, 227, 258, 0, 0
    ];

    var $$inftrees$$lext = [ /* Length codes 257..285 extra */
      16, 16, 16, 16, 16, 16, 16, 16, 17, 17, 17, 17, 18, 18, 18, 18,
      19, 19, 19, 19, 20, 20, 20, 20, 21, 21, 21, 21, 16, 72, 78
    ];

    var $$inftrees$$dbase = [ /* Distance codes 0..29 base */
      1, 2, 3, 4, 5, 7, 9, 13, 17, 25, 33, 49, 65, 97, 129, 193,
      257, 385, 513, 769, 1025, 1537, 2049, 3073, 4097, 6145,
      8193, 12289, 16385, 24577, 0, 0
    ];

    var $$inftrees$$dext = [ /* Distance codes 0..29 extra */
      16, 16, 16, 16, 17, 17, 18, 18, 19, 19, 20, 20, 21, 21, 22, 22,
      23, 23, 24, 24, 25, 25, 26, 26, 27, 27,
      28, 28, 29, 29, 64, 64
    ];

    function $$inftrees$$inflate_table(type, lens, lens_index, codes, table, table_index, work, opts) {
      var bits = opts.bits;
          //here = opts.here; /* table entry for duplication */

      var len = 0;               /* a code's length in bits */
      var sym = 0;               /* index of code symbols */
      var min = 0, max = 0;          /* minimum and maximum code lengths */
      var root = 0;              /* number of index bits for root table */
      var curr = 0;              /* number of index bits for current table */
      var drop = 0;              /* code bits to drop for sub-table */
      var left = 0;                   /* number of prefix codes available */
      var used = 0;              /* code entries in table used */
      var huff = 0;              /* Huffman code */
      var incr;              /* for incrementing code, index */
      var fill;              /* index for replicating entries */
      var low;               /* low bits for current root entry */
      var mask;              /* mask for low root bits */
      var next;             /* next available space in table */
      var base = null;     /* base value table to use */
      var base_index = 0;
    //  var shoextra;    /* extra bits table to use */
      var end;                    /* use base and extra for symbol > end */
      var count = new $$$utils$common$$.Buf16($$inftrees$$MAXBITS + 1); //[MAXBITS+1];    /* number of codes of each length */
      var offs = new $$$utils$common$$.Buf16($$inftrees$$MAXBITS + 1); //[MAXBITS+1];     /* offsets in table for each length */
      var extra = null;
      var extra_index = 0;

      var here_bits, here_op, here_val;

      /*
       Process a set of code lengths to create a canonical Huffman code.  The
       code lengths are lens[0..codes-1].  Each length corresponds to the
       symbols 0..codes-1.  The Huffman code is generated by first sorting the
       symbols by length from short to long, and retaining the symbol order
       for codes with equal lengths.  Then the code starts with all zero bits
       for the first code of the shortest length, and the codes are integer
       increments for the same length, and zeros are appended as the length
       increases.  For the deflate format, these bits are stored backwards
       from their more natural integer increment ordering, and so when the
       decoding tables are built in the large loop below, the integer codes
       are incremented backwards.

       This routine assumes, but does not check, that all of the entries in
       lens[] are in the range 0..MAXBITS.  The caller must assure this.
       1..MAXBITS is interpreted as that code length.  zero means that that
       symbol does not occur in this code.

       The codes are sorted by computing a count of codes for each length,
       creating from that a table of starting indices for each length in the
       sorted table, and then entering the symbols in order in the sorted
       table.  The sorted table is work[], with that space being provided by
       the caller.

       The length counts are used for other purposes as well, i.e. finding
       the minimum and maximum length codes, determining if there are any
       codes at all, checking for a valid set of lengths, and looking ahead
       at length counts to determine sub-table sizes when building the
       decoding tables.
       */

      /* accumulate lengths for codes (assumes lens[] all in 0..MAXBITS) */
      for (len = 0; len <= $$inftrees$$MAXBITS; len++) {
        count[len] = 0;
      }
      for (sym = 0; sym < codes; sym++) {
        count[lens[lens_index + sym]]++;
      }

      /* bound code lengths, force root to be within code lengths */
      root = bits;
      for (max = $$inftrees$$MAXBITS; max >= 1; max--) {
        if (count[max] !== 0) { break; }
      }
      if (root > max) {
        root = max;
      }
      if (max === 0) {                     /* no symbols to code at all */
        //table.op[opts.table_index] = 64;  //here.op = (var char)64;    /* invalid code marker */
        //table.bits[opts.table_index] = 1;   //here.bits = (var char)1;
        //table.val[opts.table_index++] = 0;   //here.val = (var short)0;
        table[table_index++] = (1 << 24) | (64 << 16) | 0;


        //table.op[opts.table_index] = 64;
        //table.bits[opts.table_index] = 1;
        //table.val[opts.table_index++] = 0;
        table[table_index++] = (1 << 24) | (64 << 16) | 0;

        opts.bits = 1;
        return 0;     /* no symbols, but wait for decoding to report error */
      }
      for (min = 1; min < max; min++) {
        if (count[min] !== 0) { break; }
      }
      if (root < min) {
        root = min;
      }

      /* check for an over-subscribed or incomplete set of lengths */
      left = 1;
      for (len = 1; len <= $$inftrees$$MAXBITS; len++) {
        left <<= 1;
        left -= count[len];
        if (left < 0) {
          return -1;
        }        /* over-subscribed */
      }
      if (left > 0 && (type === $$inftrees$$CODES || max !== 1)) {
        return -1;                      /* incomplete set */
      }

      /* generate offsets into symbol table for each length for sorting */
      offs[1] = 0;
      for (len = 1; len < $$inftrees$$MAXBITS; len++) {
        offs[len + 1] = offs[len] + count[len];
      }

      /* sort symbols by length, by symbol order within each length */
      for (sym = 0; sym < codes; sym++) {
        if (lens[lens_index + sym] !== 0) {
          work[offs[lens[lens_index + sym]]++] = sym;
        }
      }

      /*
       Create and fill in decoding tables.  In this loop, the table being
       filled is at next and has curr index bits.  The code being used is huff
       with length len.  That code is converted to an index by dropping drop
       bits off of the bottom.  For codes where len is less than drop + curr,
       those top drop + curr - len bits are incremented through all values to
       fill the table with replicated entries.

       root is the number of index bits for the root table.  When len exceeds
       root, sub-tables are created pointed to by the root entry with an index
       of the low root bits of huff.  This is saved in low to check for when a
       new sub-table should be started.  drop is zero when the root table is
       being filled, and drop is root when sub-tables are being filled.

       When a new sub-table is needed, it is necessary to look ahead in the
       code lengths to determine what size sub-table is needed.  The length
       counts are used for this, and so count[] is decremented as codes are
       entered in the tables.

       used keeps track of how many table entries have been allocated from the
       provided *table space.  It is checked for LENS and DIST tables against
       the constants ENOUGH_LENS and ENOUGH_DISTS to guard against changes in
       the initial root table size constants.  See the comments in inftrees.h
       for more information.

       sym increments through all symbols, and the loop terminates when
       all codes of length max, i.e. all codes, have been processed.  This
       routine permits incomplete codes, so another loop after this one fills
       in the rest of the decoding tables with invalid code markers.
       */

      /* set up for code type */
      // poor man optimization - use if-else instead of switch,
      // to avoid deopts in old v8
      if (type === $$inftrees$$CODES) {
        base = extra = work;    /* dummy value--not used */
        end = 19;

      } else if (type === $$inftrees$$LENS) {
        base = $$inftrees$$lbase;
        base_index -= 257;
        extra = $$inftrees$$lext;
        extra_index -= 257;
        end = 256;

      } else {                    /* DISTS */
        base = $$inftrees$$dbase;
        extra = $$inftrees$$dext;
        end = -1;
      }

      /* initialize opts for loop */
      huff = 0;                   /* starting code */
      sym = 0;                    /* starting code symbol */
      len = min;                  /* starting code length */
      next = table_index;              /* current table to fill in */
      curr = root;                /* current table index bits */
      drop = 0;                   /* current bits to drop from code for index */
      low = -1;                   /* trigger new sub-table when len > root */
      used = 1 << root;          /* use root table entries */
      mask = used - 1;            /* mask for comparing low */

      /* check available table space */
      if ((type === $$inftrees$$LENS && used > $$inftrees$$ENOUGH_LENS) ||
        (type === $$inftrees$$DISTS && used > $$inftrees$$ENOUGH_DISTS)) {
        return 1;
      }

      /* process all codes and make table entries */
      for (;;) {
        /* create table entry */
        here_bits = len - drop;
        if (work[sym] < end) {
          here_op = 0;
          here_val = work[sym];
        }
        else if (work[sym] > end) {
          here_op = extra[extra_index + work[sym]];
          here_val = base[base_index + work[sym]];
        }
        else {
          here_op = 32 + 64;         /* end of block */
          here_val = 0;
        }

        /* replicate for those indices with low len bits equal to huff */
        incr = 1 << (len - drop);
        fill = 1 << curr;
        min = fill;                 /* save offset to next table */
        do {
          fill -= incr;
          table[next + (huff >> drop) + fill] = (here_bits << 24) | (here_op << 16) | here_val |0;
        } while (fill !== 0);

        /* backwards increment the len-bit code huff */
        incr = 1 << (len - 1);
        while (huff & incr) {
          incr >>= 1;
        }
        if (incr !== 0) {
          huff &= incr - 1;
          huff += incr;
        } else {
          huff = 0;
        }

        /* go to next symbol, update count, len */
        sym++;
        if (--count[len] === 0) {
          if (len === max) { break; }
          len = lens[lens_index + work[sym]];
        }

        /* create new sub-table if needed */
        if (len > root && (huff & mask) !== low) {
          /* if first time, transition to sub-tables */
          if (drop === 0) {
            drop = root;
          }

          /* increment past last table */
          next += min;            /* here min is 1 << curr */

          /* determine length of next table */
          curr = len - drop;
          left = 1 << curr;
          while (curr + drop < max) {
            left -= count[curr + drop];
            if (left <= 0) { break; }
            curr++;
            left <<= 1;
          }

          /* check for enough space */
          used += 1 << curr;
          if ((type === $$inftrees$$LENS && used > $$inftrees$$ENOUGH_LENS) ||
            (type === $$inftrees$$DISTS && used > $$inftrees$$ENOUGH_DISTS)) {
            return 1;
          }

          /* point entry in root table to sub-table */
          low = huff & mask;
          /*table.op[low] = curr;
          table.bits[low] = root;
          table.val[low] = next - opts.table_index;*/
          table[low] = (root << 24) | (curr << 16) | (next - table_index) |0;
        }
      }

      /* fill in remaining table entry if code is incomplete (guaranteed to have
       at most one remaining entry, since if the code is incomplete, the
       maximum code length that was allowed to get this far is one bit) */
      if (huff !== 0) {
        //table.op[next + huff] = 64;            /* invalid code marker */
        //table.bits[next + huff] = len - drop;
        //table.val[next + huff] = 0;
        table[next + huff] = ((len - drop) << 24) | (64 << 16) |0;
      }

      /* set return parameters */
      //opts.table_index += used;
      opts.bits = root;
      return 0;
    }

    var $$inftrees$$default = $$inftrees$$inflate_table;

    var $$$vendor$pako$lib$zlib$inflate$$CODES = 0;
    var $$$vendor$pako$lib$zlib$inflate$$LENS = 1;
    var $$$vendor$pako$lib$zlib$inflate$$DISTS = 2;

    /* Public constants ==========================================================*/
    /* ===========================================================================*/


    /* Allowed flush values; see deflate() and inflate() below for details */
    //var Z_NO_FLUSH      = 0;
    //var Z_PARTIAL_FLUSH = 1;
    //var Z_SYNC_FLUSH    = 2;
    //var Z_FULL_FLUSH    = 3;
    var $$$vendor$pako$lib$zlib$inflate$$Z_FINISH        = 4;
    var $$$vendor$pako$lib$zlib$inflate$$Z_BLOCK         = 5;
    var $$$vendor$pako$lib$zlib$inflate$$Z_TREES         = 6;


    /* Return codes for the compression/decompression functions. Negative values
     * are errors, positive values are used for special but normal events.
     */
    var $$$vendor$pako$lib$zlib$inflate$$Z_OK            = 0;
    var $$$vendor$pako$lib$zlib$inflate$$Z_STREAM_END    = 1;
    var $$$vendor$pako$lib$zlib$inflate$$Z_NEED_DICT     = 2;
    //var Z_ERRNO         = -1;
    var $$$vendor$pako$lib$zlib$inflate$$Z_STREAM_ERROR  = -2;
    var $$$vendor$pako$lib$zlib$inflate$$Z_DATA_ERROR    = -3;
    var $$$vendor$pako$lib$zlib$inflate$$Z_MEM_ERROR     = -4;
    var $$$vendor$pako$lib$zlib$inflate$$Z_BUF_ERROR     = -5;
    //var Z_VERSION_ERROR = -6;

    /* The deflate compression method */
    var $$$vendor$pako$lib$zlib$inflate$$Z_DEFLATED  = 8;


    /* STATES ====================================================================*/
    /* ===========================================================================*/


    var    $$$vendor$pako$lib$zlib$inflate$$HEAD = 1;/* i: waiting for magic header */
    var    $$$vendor$pako$lib$zlib$inflate$$FLAGS = 2;/* i: waiting for method and flags (gzip) */
    var    $$$vendor$pako$lib$zlib$inflate$$TIME = 3;/* i: waiting for modification time (gzip) */
    var    $$$vendor$pako$lib$zlib$inflate$$OS = 4;/* i: waiting for extra flags and operating system (gzip) */
    var    $$$vendor$pako$lib$zlib$inflate$$EXLEN = 5;/* i: waiting for extra length (gzip) */
    var    $$$vendor$pako$lib$zlib$inflate$$EXTRA = 6;/* i: waiting for extra bytes (gzip) */
    var    $$$vendor$pako$lib$zlib$inflate$$NAME = 7;/* i: waiting for end of file name (gzip) */
    var    $$$vendor$pako$lib$zlib$inflate$$COMMENT = 8;/* i: waiting for end of comment (gzip) */
    var    $$$vendor$pako$lib$zlib$inflate$$HCRC = 9;/* i: waiting for header crc (gzip) */
    var    $$$vendor$pako$lib$zlib$inflate$$DICTID = 10;/* i: waiting for dictionary check value */
    var    $$$vendor$pako$lib$zlib$inflate$$DICT = 11;/* waiting for inflateSetDictionary() call */
    var        $$$vendor$pako$lib$zlib$inflate$$TYPE = 12;/* i: waiting for type bits, including last-flag bit */
    var        $$$vendor$pako$lib$zlib$inflate$$TYPEDO = 13;/* i: same, but skip check to exit inflate on new block */
    var        $$$vendor$pako$lib$zlib$inflate$$STORED = 14;/* i: waiting for stored size (length and complement) */
    var        $$$vendor$pako$lib$zlib$inflate$$COPY_ = 15;/* i/o: same as COPY below, but only first time in */
    var        $$$vendor$pako$lib$zlib$inflate$$COPY = 16;/* i/o: waiting for input or output to copy stored block */
    var        $$$vendor$pako$lib$zlib$inflate$$TABLE = 17;/* i: waiting for dynamic block table lengths */
    var        $$$vendor$pako$lib$zlib$inflate$$LENLENS = 18;/* i: waiting for code length code lengths */
    var        $$$vendor$pako$lib$zlib$inflate$$CODELENS = 19;/* i: waiting for length/lit and distance code lengths */
    var            $$$vendor$pako$lib$zlib$inflate$$LEN_ = 20;/* i: same as LEN below, but only first time in */
    var            $$$vendor$pako$lib$zlib$inflate$$LEN = 21;/* i: waiting for length/lit/eob code */
    var            $$$vendor$pako$lib$zlib$inflate$$LENEXT = 22;/* i: waiting for length extra bits */
    var            $$$vendor$pako$lib$zlib$inflate$$DIST = 23;/* i: waiting for distance code */
    var            $$$vendor$pako$lib$zlib$inflate$$DISTEXT = 24;/* i: waiting for distance extra bits */
    var            $$$vendor$pako$lib$zlib$inflate$$MATCH = 25;/* o: waiting for output space to copy string */
    var            $$$vendor$pako$lib$zlib$inflate$$LIT = 26;/* o: waiting for output space to write literal */
    var    $$$vendor$pako$lib$zlib$inflate$$CHECK = 27;/* i: waiting for 32-bit check value */
    var    $$$vendor$pako$lib$zlib$inflate$$LENGTH = 28;/* i: waiting for 32-bit length (gzip) */
    var    $$$vendor$pako$lib$zlib$inflate$$DONE = 29;/* finished check, done -- remain here until reset */
    var    $$$vendor$pako$lib$zlib$inflate$$BAD = 30;/* got a data error -- remain here until reset */
    var    $$$vendor$pako$lib$zlib$inflate$$MEM = 31;/* got an inflate() memory error -- remain here until reset */
    var    $$$vendor$pako$lib$zlib$inflate$$SYNC = 32;/* looking for synchronization bytes to restart inflate() */

    /* ===========================================================================*/



    var $$$vendor$pako$lib$zlib$inflate$$ENOUGH_LENS = 852;
    var $$$vendor$pako$lib$zlib$inflate$$ENOUGH_DISTS = 592;
    //var ENOUGH =  (ENOUGH_LENS+ENOUGH_DISTS);

    var $$$vendor$pako$lib$zlib$inflate$$MAX_WBITS = 15;
    /* 32K LZ77 window */
    var $$$vendor$pako$lib$zlib$inflate$$DEF_WBITS = $$$vendor$pako$lib$zlib$inflate$$MAX_WBITS;


    function $$$vendor$pako$lib$zlib$inflate$$zswap32(q) {
      return  (((q >>> 24) & 0xff) +
              ((q >>> 8) & 0xff00) +
              ((q & 0xff00) << 8) +
              ((q & 0xff) << 24));
    }


    function $$$vendor$pako$lib$zlib$inflate$$InflateState() {
      this.mode = 0;             /* current inflate mode */
      this.last = false;          /* true if processing last block */
      this.wrap = 0;              /* bit 0 true for zlib, bit 1 true for gzip */
      this.havedict = false;      /* true if dictionary provided */
      this.flags = 0;             /* gzip header method and flags (0 if zlib) */
      this.dmax = 0;              /* zlib header max distance (INFLATE_STRICT) */
      this.check = 0;             /* protected copy of check value */
      this.total = 0;             /* protected copy of output count */
      // TODO: may be {}
      this.head = null;           /* where to save gzip header information */

      /* sliding window */
      this.wbits = 0;             /* log base 2 of requested window size */
      this.wsize = 0;             /* window size or zero if not using window */
      this.whave = 0;             /* valid bytes in the window */
      this.wnext = 0;             /* window write index */
      this.window = null;         /* allocated sliding window, if needed */

      /* bit accumulator */
      this.hold = 0;              /* input bit accumulator */
      this.bits = 0;              /* number of bits in "in" */

      /* for string and stored block copying */
      this.length = 0;            /* literal or length of data to copy */
      this.offset = 0;            /* distance back to copy string from */

      /* for table and code decoding */
      this.extra = 0;             /* extra bits needed */

      /* fixed and dynamic code tables */
      this.lencode = null;          /* starting table for length/literal codes */
      this.distcode = null;         /* starting table for distance codes */
      this.lenbits = 0;           /* index bits for lencode */
      this.distbits = 0;          /* index bits for distcode */

      /* dynamic table building */
      this.ncode = 0;             /* number of code length code lengths */
      this.nlen = 0;              /* number of length code lengths */
      this.ndist = 0;             /* number of distance code lengths */
      this.have = 0;              /* number of code lengths in lens[] */
      this.next = null;              /* next available space in codes[] */

      this.lens = new $$$utils$common$$.Buf16(320); /* temporary storage for code lengths */
      this.work = new $$$utils$common$$.Buf16(288); /* work area for code table building */

      /*
       because we don't have pointers in js, we use lencode and distcode directly
       as buffers so we don't need codes
      */
      //this.codes = new utils.Buf32(ENOUGH);       /* space for code tables */
      this.lendyn = null;              /* dynamic table for length/literal codes (JS specific) */
      this.distdyn = null;             /* dynamic table for distance codes (JS specific) */
      this.sane = 0;                   /* if false, allow invalid distance too far */
      this.back = 0;                   /* bits back of last unprocessed length/lit */
      this.was = 0;                    /* initial length of match */
    }

    function $$$vendor$pako$lib$zlib$inflate$$inflateResetKeep(strm) {
      var state;

      if (!strm || !strm.state) { return $$$vendor$pako$lib$zlib$inflate$$Z_STREAM_ERROR; }
      state = strm.state;
      strm.total_in = strm.total_out = state.total = 0;
      strm.msg = ''; /*Z_NULL*/
      if (state.wrap) {       /* to support ill-conceived Java test suite */
        strm.adler = state.wrap & 1;
      }
      state.mode = $$$vendor$pako$lib$zlib$inflate$$HEAD;
      state.last = 0;
      state.havedict = 0;
      state.dmax = 32768;
      state.head = null/*Z_NULL*/;
      state.hold = 0;
      state.bits = 0;
      //state.lencode = state.distcode = state.next = state.codes;
      state.lencode = state.lendyn = new $$$utils$common$$.Buf32($$$vendor$pako$lib$zlib$inflate$$ENOUGH_LENS);
      state.distcode = state.distdyn = new $$$utils$common$$.Buf32($$$vendor$pako$lib$zlib$inflate$$ENOUGH_DISTS);

      state.sane = 1;
      state.back = -1;
      //Tracev((stderr, "inflate: reset\n"));
      return $$$vendor$pako$lib$zlib$inflate$$Z_OK;
    }

    function $$$vendor$pako$lib$zlib$inflate$$inflateReset(strm) {
      var state;

      if (!strm || !strm.state) { return $$$vendor$pako$lib$zlib$inflate$$Z_STREAM_ERROR; }
      state = strm.state;
      state.wsize = 0;
      state.whave = 0;
      state.wnext = 0;
      return $$$vendor$pako$lib$zlib$inflate$$inflateResetKeep(strm);

    }

    function $$$vendor$pako$lib$zlib$inflate$$inflateReset2(strm, windowBits) {
      var wrap;
      var state;

      /* get the state */
      if (!strm || !strm.state) { return $$$vendor$pako$lib$zlib$inflate$$Z_STREAM_ERROR; }
      state = strm.state;

      /* extract wrap request from windowBits parameter */
      if (windowBits < 0) {
        wrap = 0;
        windowBits = -windowBits;
      }
      else {
        wrap = (windowBits >> 4) + 1;
        if (windowBits < 48) {
          windowBits &= 15;
        }
      }

      /* set number of window bits, free window if different */
      if (windowBits && (windowBits < 8 || windowBits > 15)) {
        return $$$vendor$pako$lib$zlib$inflate$$Z_STREAM_ERROR;
      }
      if (state.window !== null && state.wbits !== windowBits) {
        state.window = null;
      }

      /* update state and reset the rest of it */
      state.wrap = wrap;
      state.wbits = windowBits;
      return $$$vendor$pako$lib$zlib$inflate$$inflateReset(strm);
    }

    function $$$vendor$pako$lib$zlib$inflate$$inflateInit2(strm, windowBits) {
      var ret;
      var state;

      if (!strm) { return $$$vendor$pako$lib$zlib$inflate$$Z_STREAM_ERROR; }
      //strm.msg = Z_NULL;                 /* in case we return an error */

      state = new $$$vendor$pako$lib$zlib$inflate$$InflateState();

      //if (state === Z_NULL) return Z_MEM_ERROR;
      //Tracev((stderr, "inflate: allocated\n"));
      strm.state = state;
      state.window = null/*Z_NULL*/;
      ret = $$$vendor$pako$lib$zlib$inflate$$inflateReset2(strm, windowBits);
      if (ret !== $$$vendor$pako$lib$zlib$inflate$$Z_OK) {
        strm.state = null/*Z_NULL*/;
      }
      return ret;
    }

    function $$$vendor$pako$lib$zlib$inflate$$inflateInit(strm) {
      return $$$vendor$pako$lib$zlib$inflate$$inflateInit2(strm, $$$vendor$pako$lib$zlib$inflate$$DEF_WBITS);
    }


    /*
     Return state with length and distance decoding tables and index sizes set to
     fixed code decoding.  Normally this returns fixed tables from inffixed.h.
     If BUILDFIXED is defined, then instead this routine builds the tables the
     first time it's called, and returns those tables the first time and
     thereafter.  This reduces the size of the code by about 2K bytes, in
     exchange for a little execution time.  However, BUILDFIXED should not be
     used for threaded applications, since the rewriting of the tables and virgin
     may not be thread-safe.
     */
    var $$$vendor$pako$lib$zlib$inflate$$virgin = true;

    var $$$vendor$pako$lib$zlib$inflate$$lenfix, $$$vendor$pako$lib$zlib$inflate$$distfix; // We have no pointers in JS, so keep tables separate

    function $$$vendor$pako$lib$zlib$inflate$$fixedtables(state) {
      /* build fixed huffman tables if first call (may not be thread safe) */
      if ($$$vendor$pako$lib$zlib$inflate$$virgin) {
        var sym;

        $$$vendor$pako$lib$zlib$inflate$$lenfix = new $$$utils$common$$.Buf32(512);
        $$$vendor$pako$lib$zlib$inflate$$distfix = new $$$utils$common$$.Buf32(32);

        /* literal/length table */
        sym = 0;
        while (sym < 144) { state.lens[sym++] = 8; }
        while (sym < 256) { state.lens[sym++] = 9; }
        while (sym < 280) { state.lens[sym++] = 7; }
        while (sym < 288) { state.lens[sym++] = 8; }

        $$inftrees$$default($$$vendor$pako$lib$zlib$inflate$$LENS,  state.lens, 0, 288, $$$vendor$pako$lib$zlib$inflate$$lenfix,   0, state.work, { bits: 9 });

        /* distance table */
        sym = 0;
        while (sym < 32) { state.lens[sym++] = 5; }

        $$inftrees$$default($$$vendor$pako$lib$zlib$inflate$$DISTS, state.lens, 0, 32,   $$$vendor$pako$lib$zlib$inflate$$distfix, 0, state.work, { bits: 5 });

        /* do this just once */
        $$$vendor$pako$lib$zlib$inflate$$virgin = false;
      }

      state.lencode = $$$vendor$pako$lib$zlib$inflate$$lenfix;
      state.lenbits = 9;
      state.distcode = $$$vendor$pako$lib$zlib$inflate$$distfix;
      state.distbits = 5;
    }


    /*
     Update the window with the last wsize (normally 32K) bytes written before
     returning.  If window does not exist yet, create it.  This is only called
     when a window is already in use, or when output has been written during this
     inflate call, but the end of the deflate stream has not been reached yet.
     It is also called to create a window for dictionary data when a dictionary
     is loaded.

     Providing output buffers larger than 32K to inflate() should provide a speed
     advantage, since only the last 32K of output is copied to the sliding window
     upon return from inflate(), and since all distances after the first 32K of
     output will fall in the output data, making match copies simpler and faster.
     The advantage may be dependent on the size of the processor's data caches.
     */
    function $$$vendor$pako$lib$zlib$inflate$$updatewindow(strm, src, end, copy) {
      var dist;
      var state = strm.state;

      /* if it hasn't been done already, allocate space for the window */
      if (state.window === null) {
        state.wsize = 1 << state.wbits;
        state.wnext = 0;
        state.whave = 0;

        state.window = new $$$utils$common$$.Buf8(state.wsize);
      }

      /* copy state->wsize or less output bytes into the circular window */
      if (copy >= state.wsize) {
        $$$utils$common$$.arraySet(state.window, src, end - state.wsize, state.wsize, 0);
        state.wnext = 0;
        state.whave = state.wsize;
      }
      else {
        dist = state.wsize - state.wnext;
        if (dist > copy) {
          dist = copy;
        }
        //zmemcpy(state->window + state->wnext, end - copy, dist);
        $$$utils$common$$.arraySet(state.window, src, end - copy, dist, state.wnext);
        copy -= dist;
        if (copy) {
          //zmemcpy(state->window, end - copy, copy);
          $$$utils$common$$.arraySet(state.window, src, end - copy, copy, 0);
          state.wnext = copy;
          state.whave = state.wsize;
        }
        else {
          state.wnext += dist;
          if (state.wnext === state.wsize) { state.wnext = 0; }
          if (state.whave < state.wsize) { state.whave += dist; }
        }
      }
      return 0;
    }

    function $$$vendor$pako$lib$zlib$inflate$$inflate(strm, flush) {
      var state;
      var input, output;          // input/output buffers
      var next;                   /* next input INDEX */
      var put;                    /* next output INDEX */
      var have, left;             /* available input and output */
      var hold;                   /* bit buffer */
      var bits;                   /* bits in bit buffer */
      var _in, _out;              /* save starting available input and output */
      var copy;                   /* number of stored or match bytes to copy */
      var from;                   /* where to copy match bytes from */
      var from_source;
      var here = 0;               /* current decoding table entry */
      var here_bits, here_op, here_val; // paked "here" denormalized (JS specific)
      //var last;                   /* parent table entry */
      var last_bits, last_op, last_val; // paked "last" denormalized (JS specific)
      var len;                    /* length to copy for repeats, bits to drop */
      var ret;                    /* return code */
      var hbuf = new $$$utils$common$$.Buf8(4);    /* buffer for gzip header crc calculation */
      var opts;

      var n; // temporary var for NEED_BITS

      var order = /* permutation of code lengths */
        [ 16, 17, 18, 0, 8, 7, 9, 6, 10, 5, 11, 4, 12, 3, 13, 2, 14, 1, 15 ];


      if (!strm || !strm.state || !strm.output ||
          (!strm.input && strm.avail_in !== 0)) {
        return $$$vendor$pako$lib$zlib$inflate$$Z_STREAM_ERROR;
      }

      state = strm.state;
      if (state.mode === $$$vendor$pako$lib$zlib$inflate$$TYPE) { state.mode = $$$vendor$pako$lib$zlib$inflate$$TYPEDO; }    /* skip check */


      //--- LOAD() ---
      put = strm.next_out;
      output = strm.output;
      left = strm.avail_out;
      next = strm.next_in;
      input = strm.input;
      have = strm.avail_in;
      hold = state.hold;
      bits = state.bits;
      //---

      _in = have;
      _out = left;
      ret = $$$vendor$pako$lib$zlib$inflate$$Z_OK;

      inf_leave: // goto emulation
      for (;;) {
        switch (state.mode) {
        case $$$vendor$pako$lib$zlib$inflate$$HEAD:
          if (state.wrap === 0) {
            state.mode = $$$vendor$pako$lib$zlib$inflate$$TYPEDO;
            break;
          }
          //=== NEEDBITS(16);
          while (bits < 16) {
            if (have === 0) { break inf_leave; }
            have--;
            hold += input[next++] << bits;
            bits += 8;
          }
          //===//
          if ((state.wrap & 2) && hold === 0x8b1f) {  /* gzip header */
            state.check = 0/*crc32(0L, Z_NULL, 0)*/;
            //=== CRC2(state.check, hold);
            hbuf[0] = hold & 0xff;
            hbuf[1] = (hold >>> 8) & 0xff;
            state.check = $$crc32$$default(state.check, hbuf, 2, 0);
            //===//

            //=== INITBITS();
            hold = 0;
            bits = 0;
            //===//
            state.mode = $$$vendor$pako$lib$zlib$inflate$$FLAGS;
            break;
          }
          state.flags = 0;           /* expect zlib header */
          if (state.head) {
            state.head.done = false;
          }
          if (!(state.wrap & 1) ||   /* check if zlib header allowed */
            (((hold & 0xff)/*BITS(8)*/ << 8) + (hold >> 8)) % 31) {
            strm.msg = 'incorrect header check';
            state.mode = $$$vendor$pako$lib$zlib$inflate$$BAD;
            break;
          }
          if ((hold & 0x0f)/*BITS(4)*/ !== $$$vendor$pako$lib$zlib$inflate$$Z_DEFLATED) {
            strm.msg = 'unknown compression method';
            state.mode = $$$vendor$pako$lib$zlib$inflate$$BAD;
            break;
          }
          //--- DROPBITS(4) ---//
          hold >>>= 4;
          bits -= 4;
          //---//
          len = (hold & 0x0f)/*BITS(4)*/ + 8;
          if (state.wbits === 0) {
            state.wbits = len;
          }
          else if (len > state.wbits) {
            strm.msg = 'invalid window size';
            state.mode = $$$vendor$pako$lib$zlib$inflate$$BAD;
            break;
          }
          state.dmax = 1 << len;
          //Tracev((stderr, "inflate:   zlib header ok\n"));
          strm.adler = state.check = 1/*adler32(0L, Z_NULL, 0)*/;
          state.mode = hold & 0x200 ? $$$vendor$pako$lib$zlib$inflate$$DICTID : $$$vendor$pako$lib$zlib$inflate$$TYPE;
          //=== INITBITS();
          hold = 0;
          bits = 0;
          //===//
          break;
        case $$$vendor$pako$lib$zlib$inflate$$FLAGS:
          //=== NEEDBITS(16); */
          while (bits < 16) {
            if (have === 0) { break inf_leave; }
            have--;
            hold += input[next++] << bits;
            bits += 8;
          }
          //===//
          state.flags = hold;
          if ((state.flags & 0xff) !== $$$vendor$pako$lib$zlib$inflate$$Z_DEFLATED) {
            strm.msg = 'unknown compression method';
            state.mode = $$$vendor$pako$lib$zlib$inflate$$BAD;
            break;
          }
          if (state.flags & 0xe000) {
            strm.msg = 'unknown header flags set';
            state.mode = $$$vendor$pako$lib$zlib$inflate$$BAD;
            break;
          }
          if (state.head) {
            state.head.text = ((hold >> 8) & 1);
          }
          if (state.flags & 0x0200) {
            //=== CRC2(state.check, hold);
            hbuf[0] = hold & 0xff;
            hbuf[1] = (hold >>> 8) & 0xff;
            state.check = $$crc32$$default(state.check, hbuf, 2, 0);
            //===//
          }
          //=== INITBITS();
          hold = 0;
          bits = 0;
          //===//
          state.mode = $$$vendor$pako$lib$zlib$inflate$$TIME;
          /* falls through */
        case $$$vendor$pako$lib$zlib$inflate$$TIME:
          //=== NEEDBITS(32); */
          while (bits < 32) {
            if (have === 0) { break inf_leave; }
            have--;
            hold += input[next++] << bits;
            bits += 8;
          }
          //===//
          if (state.head) {
            state.head.time = hold;
          }
          if (state.flags & 0x0200) {
            //=== CRC4(state.check, hold)
            hbuf[0] = hold & 0xff;
            hbuf[1] = (hold >>> 8) & 0xff;
            hbuf[2] = (hold >>> 16) & 0xff;
            hbuf[3] = (hold >>> 24) & 0xff;
            state.check = $$crc32$$default(state.check, hbuf, 4, 0);
            //===
          }
          //=== INITBITS();
          hold = 0;
          bits = 0;
          //===//
          state.mode = $$$vendor$pako$lib$zlib$inflate$$OS;
          /* falls through */
        case $$$vendor$pako$lib$zlib$inflate$$OS:
          //=== NEEDBITS(16); */
          while (bits < 16) {
            if (have === 0) { break inf_leave; }
            have--;
            hold += input[next++] << bits;
            bits += 8;
          }
          //===//
          if (state.head) {
            state.head.xflags = (hold & 0xff);
            state.head.os = (hold >> 8);
          }
          if (state.flags & 0x0200) {
            //=== CRC2(state.check, hold);
            hbuf[0] = hold & 0xff;
            hbuf[1] = (hold >>> 8) & 0xff;
            state.check = $$crc32$$default(state.check, hbuf, 2, 0);
            //===//
          }
          //=== INITBITS();
          hold = 0;
          bits = 0;
          //===//
          state.mode = $$$vendor$pako$lib$zlib$inflate$$EXLEN;
          /* falls through */
        case $$$vendor$pako$lib$zlib$inflate$$EXLEN:
          if (state.flags & 0x0400) {
            //=== NEEDBITS(16); */
            while (bits < 16) {
              if (have === 0) { break inf_leave; }
              have--;
              hold += input[next++] << bits;
              bits += 8;
            }
            //===//
            state.length = hold;
            if (state.head) {
              state.head.extra_len = hold;
            }
            if (state.flags & 0x0200) {
              //=== CRC2(state.check, hold);
              hbuf[0] = hold & 0xff;
              hbuf[1] = (hold >>> 8) & 0xff;
              state.check = $$crc32$$default(state.check, hbuf, 2, 0);
              //===//
            }
            //=== INITBITS();
            hold = 0;
            bits = 0;
            //===//
          }
          else if (state.head) {
            state.head.extra = null/*Z_NULL*/;
          }
          state.mode = $$$vendor$pako$lib$zlib$inflate$$EXTRA;
          /* falls through */
        case $$$vendor$pako$lib$zlib$inflate$$EXTRA:
          if (state.flags & 0x0400) {
            copy = state.length;
            if (copy > have) { copy = have; }
            if (copy) {
              if (state.head) {
                len = state.head.extra_len - state.length;
                if (!state.head.extra) {
                  // Use untyped array for more conveniend processing later
                  state.head.extra = new Array(state.head.extra_len);
                }
                $$$utils$common$$.arraySet(
                  state.head.extra,
                  input,
                  next,
                  // extra field is limited to 65536 bytes
                  // - no need for additional size check
                  copy,
                  /*len + copy > state.head.extra_max - len ? state.head.extra_max : copy,*/
                  len
                );
                //zmemcpy(state.head.extra + len, next,
                //        len + copy > state.head.extra_max ?
                //        state.head.extra_max - len : copy);
              }
              if (state.flags & 0x0200) {
                state.check = $$crc32$$default(state.check, input, copy, next);
              }
              have -= copy;
              next += copy;
              state.length -= copy;
            }
            if (state.length) { break inf_leave; }
          }
          state.length = 0;
          state.mode = $$$vendor$pako$lib$zlib$inflate$$NAME;
          /* falls through */
        case $$$vendor$pako$lib$zlib$inflate$$NAME:
          if (state.flags & 0x0800) {
            if (have === 0) { break inf_leave; }
            copy = 0;
            do {
              // TODO: 2 or 1 bytes?
              len = input[next + copy++];
              /* use constant limit because in js we should not preallocate memory */
              if (state.head && len &&
                  (state.length < 65536 /*state.head.name_max*/)) {
                state.head.name += String.fromCharCode(len);
              }
            } while (len && copy < have);

            if (state.flags & 0x0200) {
              state.check = $$crc32$$default(state.check, input, copy, next);
            }
            have -= copy;
            next += copy;
            if (len) { break inf_leave; }
          }
          else if (state.head) {
            state.head.name = null;
          }
          state.length = 0;
          state.mode = $$$vendor$pako$lib$zlib$inflate$$COMMENT;
          /* falls through */
        case $$$vendor$pako$lib$zlib$inflate$$COMMENT:
          if (state.flags & 0x1000) {
            if (have === 0) { break inf_leave; }
            copy = 0;
            do {
              len = input[next + copy++];
              /* use constant limit because in js we should not preallocate memory */
              if (state.head && len &&
                  (state.length < 65536 /*state.head.comm_max*/)) {
                state.head.comment += String.fromCharCode(len);
              }
            } while (len && copy < have);
            if (state.flags & 0x0200) {
              state.check = $$crc32$$default(state.check, input, copy, next);
            }
            have -= copy;
            next += copy;
            if (len) { break inf_leave; }
          }
          else if (state.head) {
            state.head.comment = null;
          }
          state.mode = $$$vendor$pako$lib$zlib$inflate$$HCRC;
          /* falls through */
        case $$$vendor$pako$lib$zlib$inflate$$HCRC:
          if (state.flags & 0x0200) {
            //=== NEEDBITS(16); */
            while (bits < 16) {
              if (have === 0) { break inf_leave; }
              have--;
              hold += input[next++] << bits;
              bits += 8;
            }
            //===//
            if (hold !== (state.check & 0xffff)) {
              strm.msg = 'header crc mismatch';
              state.mode = $$$vendor$pako$lib$zlib$inflate$$BAD;
              break;
            }
            //=== INITBITS();
            hold = 0;
            bits = 0;
            //===//
          }
          if (state.head) {
            state.head.hcrc = ((state.flags >> 9) & 1);
            state.head.done = true;
          }
          strm.adler = state.check = 0;
          state.mode = $$$vendor$pako$lib$zlib$inflate$$TYPE;
          break;
        case $$$vendor$pako$lib$zlib$inflate$$DICTID:
          //=== NEEDBITS(32); */
          while (bits < 32) {
            if (have === 0) { break inf_leave; }
            have--;
            hold += input[next++] << bits;
            bits += 8;
          }
          //===//
          strm.adler = state.check = $$$vendor$pako$lib$zlib$inflate$$zswap32(hold);
          //=== INITBITS();
          hold = 0;
          bits = 0;
          //===//
          state.mode = $$$vendor$pako$lib$zlib$inflate$$DICT;
          /* falls through */
        case $$$vendor$pako$lib$zlib$inflate$$DICT:
          if (state.havedict === 0) {
            //--- RESTORE() ---
            strm.next_out = put;
            strm.avail_out = left;
            strm.next_in = next;
            strm.avail_in = have;
            state.hold = hold;
            state.bits = bits;
            //---
            return $$$vendor$pako$lib$zlib$inflate$$Z_NEED_DICT;
          }
          strm.adler = state.check = 1/*adler32(0L, Z_NULL, 0)*/;
          state.mode = $$$vendor$pako$lib$zlib$inflate$$TYPE;
          /* falls through */
        case $$$vendor$pako$lib$zlib$inflate$$TYPE:
          if (flush === $$$vendor$pako$lib$zlib$inflate$$Z_BLOCK || flush === $$$vendor$pako$lib$zlib$inflate$$Z_TREES) { break inf_leave; }
          /* falls through */
        case $$$vendor$pako$lib$zlib$inflate$$TYPEDO:
          if (state.last) {
            //--- BYTEBITS() ---//
            hold >>>= bits & 7;
            bits -= bits & 7;
            //---//
            state.mode = $$$vendor$pako$lib$zlib$inflate$$CHECK;
            break;
          }
          //=== NEEDBITS(3); */
          while (bits < 3) {
            if (have === 0) { break inf_leave; }
            have--;
            hold += input[next++] << bits;
            bits += 8;
          }
          //===//
          state.last = (hold & 0x01)/*BITS(1)*/;
          //--- DROPBITS(1) ---//
          hold >>>= 1;
          bits -= 1;
          //---//

          switch ((hold & 0x03)/*BITS(2)*/) {
          case 0:                             /* stored block */
            //Tracev((stderr, "inflate:     stored block%s\n",
            //        state.last ? " (last)" : ""));
            state.mode = $$$vendor$pako$lib$zlib$inflate$$STORED;
            break;
          case 1:                             /* fixed block */
            $$$vendor$pako$lib$zlib$inflate$$fixedtables(state);
            //Tracev((stderr, "inflate:     fixed codes block%s\n",
            //        state.last ? " (last)" : ""));
            state.mode = $$$vendor$pako$lib$zlib$inflate$$LEN_;             /* decode codes */
            if (flush === $$$vendor$pako$lib$zlib$inflate$$Z_TREES) {
              //--- DROPBITS(2) ---//
              hold >>>= 2;
              bits -= 2;
              //---//
              break inf_leave;
            }
            break;
          case 2:                             /* dynamic block */
            //Tracev((stderr, "inflate:     dynamic codes block%s\n",
            //        state.last ? " (last)" : ""));
            state.mode = $$$vendor$pako$lib$zlib$inflate$$TABLE;
            break;
          case 3:
            strm.msg = 'invalid block type';
            state.mode = $$$vendor$pako$lib$zlib$inflate$$BAD;
          }
          //--- DROPBITS(2) ---//
          hold >>>= 2;
          bits -= 2;
          //---//
          break;
        case $$$vendor$pako$lib$zlib$inflate$$STORED:
          //--- BYTEBITS() ---// /* go to byte boundary */
          hold >>>= bits & 7;
          bits -= bits & 7;
          //---//
          //=== NEEDBITS(32); */
          while (bits < 32) {
            if (have === 0) { break inf_leave; }
            have--;
            hold += input[next++] << bits;
            bits += 8;
          }
          //===//
          if ((hold & 0xffff) !== ((hold >>> 16) ^ 0xffff)) {
            strm.msg = 'invalid stored block lengths';
            state.mode = $$$vendor$pako$lib$zlib$inflate$$BAD;
            break;
          }
          state.length = hold & 0xffff;
          //Tracev((stderr, "inflate:       stored length %u\n",
          //        state.length));
          //=== INITBITS();
          hold = 0;
          bits = 0;
          //===//
          state.mode = $$$vendor$pako$lib$zlib$inflate$$COPY_;
          if (flush === $$$vendor$pako$lib$zlib$inflate$$Z_TREES) { break inf_leave; }
          /* falls through */
        case $$$vendor$pako$lib$zlib$inflate$$COPY_:
          state.mode = $$$vendor$pako$lib$zlib$inflate$$COPY;
          /* falls through */
        case $$$vendor$pako$lib$zlib$inflate$$COPY:
          copy = state.length;
          if (copy) {
            if (copy > have) { copy = have; }
            if (copy > left) { copy = left; }
            if (copy === 0) { break inf_leave; }
            //--- zmemcpy(put, next, copy); ---
            $$$utils$common$$.arraySet(output, input, next, copy, put);
            //---//
            have -= copy;
            next += copy;
            left -= copy;
            put += copy;
            state.length -= copy;
            break;
          }
          //Tracev((stderr, "inflate:       stored end\n"));
          state.mode = $$$vendor$pako$lib$zlib$inflate$$TYPE;
          break;
        case $$$vendor$pako$lib$zlib$inflate$$TABLE:
          //=== NEEDBITS(14); */
          while (bits < 14) {
            if (have === 0) { break inf_leave; }
            have--;
            hold += input[next++] << bits;
            bits += 8;
          }
          //===//
          state.nlen = (hold & 0x1f)/*BITS(5)*/ + 257;
          //--- DROPBITS(5) ---//
          hold >>>= 5;
          bits -= 5;
          //---//
          state.ndist = (hold & 0x1f)/*BITS(5)*/ + 1;
          //--- DROPBITS(5) ---//
          hold >>>= 5;
          bits -= 5;
          //---//
          state.ncode = (hold & 0x0f)/*BITS(4)*/ + 4;
          //--- DROPBITS(4) ---//
          hold >>>= 4;
          bits -= 4;
          //---//
    //#ifndef PKZIP_BUG_WORKAROUND
          if (state.nlen > 286 || state.ndist > 30) {
            strm.msg = 'too many length or distance symbols';
            state.mode = $$$vendor$pako$lib$zlib$inflate$$BAD;
            break;
          }
    //#endif
          //Tracev((stderr, "inflate:       table sizes ok\n"));
          state.have = 0;
          state.mode = $$$vendor$pako$lib$zlib$inflate$$LENLENS;
          /* falls through */
        case $$$vendor$pako$lib$zlib$inflate$$LENLENS:
          while (state.have < state.ncode) {
            //=== NEEDBITS(3);
            while (bits < 3) {
              if (have === 0) { break inf_leave; }
              have--;
              hold += input[next++] << bits;
              bits += 8;
            }
            //===//
            state.lens[order[state.have++]] = (hold & 0x07);//BITS(3);
            //--- DROPBITS(3) ---//
            hold >>>= 3;
            bits -= 3;
            //---//
          }
          while (state.have < 19) {
            state.lens[order[state.have++]] = 0;
          }
          // We have separate tables & no pointers. 2 commented lines below not needed.
          //state.next = state.codes;
          //state.lencode = state.next;
          // Switch to use dynamic table
          state.lencode = state.lendyn;
          state.lenbits = 7;

          opts = { bits: state.lenbits };
          ret = $$inftrees$$default($$$vendor$pako$lib$zlib$inflate$$CODES, state.lens, 0, 19, state.lencode, 0, state.work, opts);
          state.lenbits = opts.bits;

          if (ret) {
            strm.msg = 'invalid code lengths set';
            state.mode = $$$vendor$pako$lib$zlib$inflate$$BAD;
            break;
          }
          //Tracev((stderr, "inflate:       code lengths ok\n"));
          state.have = 0;
          state.mode = $$$vendor$pako$lib$zlib$inflate$$CODELENS;
          /* falls through */
        case $$$vendor$pako$lib$zlib$inflate$$CODELENS:
          while (state.have < state.nlen + state.ndist) {
            for (;;) {
              here = state.lencode[hold & ((1 << state.lenbits) - 1)];/*BITS(state.lenbits)*/
              here_bits = here >>> 24;
              here_op = (here >>> 16) & 0xff;
              here_val = here & 0xffff;

              if ((here_bits) <= bits) { break; }
              //--- PULLBYTE() ---//
              if (have === 0) { break inf_leave; }
              have--;
              hold += input[next++] << bits;
              bits += 8;
              //---//
            }
            if (here_val < 16) {
              //--- DROPBITS(here.bits) ---//
              hold >>>= here_bits;
              bits -= here_bits;
              //---//
              state.lens[state.have++] = here_val;
            }
            else {
              if (here_val === 16) {
                //=== NEEDBITS(here.bits + 2);
                n = here_bits + 2;
                while (bits < n) {
                  if (have === 0) { break inf_leave; }
                  have--;
                  hold += input[next++] << bits;
                  bits += 8;
                }
                //===//
                //--- DROPBITS(here.bits) ---//
                hold >>>= here_bits;
                bits -= here_bits;
                //---//
                if (state.have === 0) {
                  strm.msg = 'invalid bit length repeat';
                  state.mode = $$$vendor$pako$lib$zlib$inflate$$BAD;
                  break;
                }
                len = state.lens[state.have - 1];
                copy = 3 + (hold & 0x03);//BITS(2);
                //--- DROPBITS(2) ---//
                hold >>>= 2;
                bits -= 2;
                //---//
              }
              else if (here_val === 17) {
                //=== NEEDBITS(here.bits + 3);
                n = here_bits + 3;
                while (bits < n) {
                  if (have === 0) { break inf_leave; }
                  have--;
                  hold += input[next++] << bits;
                  bits += 8;
                }
                //===//
                //--- DROPBITS(here.bits) ---//
                hold >>>= here_bits;
                bits -= here_bits;
                //---//
                len = 0;
                copy = 3 + (hold & 0x07);//BITS(3);
                //--- DROPBITS(3) ---//
                hold >>>= 3;
                bits -= 3;
                //---//
              }
              else {
                //=== NEEDBITS(here.bits + 7);
                n = here_bits + 7;
                while (bits < n) {
                  if (have === 0) { break inf_leave; }
                  have--;
                  hold += input[next++] << bits;
                  bits += 8;
                }
                //===//
                //--- DROPBITS(here.bits) ---//
                hold >>>= here_bits;
                bits -= here_bits;
                //---//
                len = 0;
                copy = 11 + (hold & 0x7f);//BITS(7);
                //--- DROPBITS(7) ---//
                hold >>>= 7;
                bits -= 7;
                //---//
              }
              if (state.have + copy > state.nlen + state.ndist) {
                strm.msg = 'invalid bit length repeat';
                state.mode = $$$vendor$pako$lib$zlib$inflate$$BAD;
                break;
              }
              while (copy--) {
                state.lens[state.have++] = len;
              }
            }
          }

          /* handle error breaks in while */
          if (state.mode === $$$vendor$pako$lib$zlib$inflate$$BAD) { break; }

          /* check for end-of-block code (better have one) */
          if (state.lens[256] === 0) {
            strm.msg = 'invalid code -- missing end-of-block';
            state.mode = $$$vendor$pako$lib$zlib$inflate$$BAD;
            break;
          }

          /* build code tables -- note: do not change the lenbits or distbits
             values here (9 and 6) without reading the comments in inftrees.h
             concerning the ENOUGH constants, which depend on those values */
          state.lenbits = 9;

          opts = { bits: state.lenbits };
          ret = $$inftrees$$default($$$vendor$pako$lib$zlib$inflate$$LENS, state.lens, 0, state.nlen, state.lencode, 0, state.work, opts);
          // We have separate tables & no pointers. 2 commented lines below not needed.
          // state.next_index = opts.table_index;
          state.lenbits = opts.bits;
          // state.lencode = state.next;

          if (ret) {
            strm.msg = 'invalid literal/lengths set';
            state.mode = $$$vendor$pako$lib$zlib$inflate$$BAD;
            break;
          }

          state.distbits = 6;
          //state.distcode.copy(state.codes);
          // Switch to use dynamic table
          state.distcode = state.distdyn;
          opts = { bits: state.distbits };
          ret = $$inftrees$$default($$$vendor$pako$lib$zlib$inflate$$DISTS, state.lens, state.nlen, state.ndist, state.distcode, 0, state.work, opts);
          // We have separate tables & no pointers. 2 commented lines below not needed.
          // state.next_index = opts.table_index;
          state.distbits = opts.bits;
          // state.distcode = state.next;

          if (ret) {
            strm.msg = 'invalid distances set';
            state.mode = $$$vendor$pako$lib$zlib$inflate$$BAD;
            break;
          }
          //Tracev((stderr, 'inflate:       codes ok\n'));
          state.mode = $$$vendor$pako$lib$zlib$inflate$$LEN_;
          if (flush === $$$vendor$pako$lib$zlib$inflate$$Z_TREES) { break inf_leave; }
          /* falls through */
        case $$$vendor$pako$lib$zlib$inflate$$LEN_:
          state.mode = $$$vendor$pako$lib$zlib$inflate$$LEN;
          /* falls through */
        case $$$vendor$pako$lib$zlib$inflate$$LEN:
          if (have >= 6 && left >= 258) {
            //--- RESTORE() ---
            strm.next_out = put;
            strm.avail_out = left;
            strm.next_in = next;
            strm.avail_in = have;
            state.hold = hold;
            state.bits = bits;
            //---
            $$inffast$$default(strm, _out);
            //--- LOAD() ---
            put = strm.next_out;
            output = strm.output;
            left = strm.avail_out;
            next = strm.next_in;
            input = strm.input;
            have = strm.avail_in;
            hold = state.hold;
            bits = state.bits;
            //---

            if (state.mode === $$$vendor$pako$lib$zlib$inflate$$TYPE) {
              state.back = -1;
            }
            break;
          }
          state.back = 0;
          for (;;) {
            here = state.lencode[hold & ((1 << state.lenbits) - 1)];  /*BITS(state.lenbits)*/
            here_bits = here >>> 24;
            here_op = (here >>> 16) & 0xff;
            here_val = here & 0xffff;

            if (here_bits <= bits) { break; }
            //--- PULLBYTE() ---//
            if (have === 0) { break inf_leave; }
            have--;
            hold += input[next++] << bits;
            bits += 8;
            //---//
          }
          if (here_op && (here_op & 0xf0) === 0) {
            last_bits = here_bits;
            last_op = here_op;
            last_val = here_val;
            for (;;) {
              here = state.lencode[last_val +
                      ((hold & ((1 << (last_bits + last_op)) - 1))/*BITS(last.bits + last.op)*/ >> last_bits)];
              here_bits = here >>> 24;
              here_op = (here >>> 16) & 0xff;
              here_val = here & 0xffff;

              if ((last_bits + here_bits) <= bits) { break; }
              //--- PULLBYTE() ---//
              if (have === 0) { break inf_leave; }
              have--;
              hold += input[next++] << bits;
              bits += 8;
              //---//
            }
            //--- DROPBITS(last.bits) ---//
            hold >>>= last_bits;
            bits -= last_bits;
            //---//
            state.back += last_bits;
          }
          //--- DROPBITS(here.bits) ---//
          hold >>>= here_bits;
          bits -= here_bits;
          //---//
          state.back += here_bits;
          state.length = here_val;
          if (here_op === 0) {
            //Tracevv((stderr, here.val >= 0x20 && here.val < 0x7f ?
            //        "inflate:         literal '%c'\n" :
            //        "inflate:         literal 0x%02x\n", here.val));
            state.mode = $$$vendor$pako$lib$zlib$inflate$$LIT;
            break;
          }
          if (here_op & 32) {
            //Tracevv((stderr, "inflate:         end of block\n"));
            state.back = -1;
            state.mode = $$$vendor$pako$lib$zlib$inflate$$TYPE;
            break;
          }
          if (here_op & 64) {
            strm.msg = 'invalid literal/length code';
            state.mode = $$$vendor$pako$lib$zlib$inflate$$BAD;
            break;
          }
          state.extra = here_op & 15;
          state.mode = $$$vendor$pako$lib$zlib$inflate$$LENEXT;
          /* falls through */
        case $$$vendor$pako$lib$zlib$inflate$$LENEXT:
          if (state.extra) {
            //=== NEEDBITS(state.extra);
            n = state.extra;
            while (bits < n) {
              if (have === 0) { break inf_leave; }
              have--;
              hold += input[next++] << bits;
              bits += 8;
            }
            //===//
            state.length += hold & ((1 << state.extra) - 1)/*BITS(state.extra)*/;
            //--- DROPBITS(state.extra) ---//
            hold >>>= state.extra;
            bits -= state.extra;
            //---//
            state.back += state.extra;
          }
          //Tracevv((stderr, "inflate:         length %u\n", state.length));
          state.was = state.length;
          state.mode = $$$vendor$pako$lib$zlib$inflate$$DIST;
          /* falls through */
        case $$$vendor$pako$lib$zlib$inflate$$DIST:
          for (;;) {
            here = state.distcode[hold & ((1 << state.distbits) - 1)];/*BITS(state.distbits)*/
            here_bits = here >>> 24;
            here_op = (here >>> 16) & 0xff;
            here_val = here & 0xffff;

            if ((here_bits) <= bits) { break; }
            //--- PULLBYTE() ---//
            if (have === 0) { break inf_leave; }
            have--;
            hold += input[next++] << bits;
            bits += 8;
            //---//
          }
          if ((here_op & 0xf0) === 0) {
            last_bits = here_bits;
            last_op = here_op;
            last_val = here_val;
            for (;;) {
              here = state.distcode[last_val +
                      ((hold & ((1 << (last_bits + last_op)) - 1))/*BITS(last.bits + last.op)*/ >> last_bits)];
              here_bits = here >>> 24;
              here_op = (here >>> 16) & 0xff;
              here_val = here & 0xffff;

              if ((last_bits + here_bits) <= bits) { break; }
              //--- PULLBYTE() ---//
              if (have === 0) { break inf_leave; }
              have--;
              hold += input[next++] << bits;
              bits += 8;
              //---//
            }
            //--- DROPBITS(last.bits) ---//
            hold >>>= last_bits;
            bits -= last_bits;
            //---//
            state.back += last_bits;
          }
          //--- DROPBITS(here.bits) ---//
          hold >>>= here_bits;
          bits -= here_bits;
          //---//
          state.back += here_bits;
          if (here_op & 64) {
            strm.msg = 'invalid distance code';
            state.mode = $$$vendor$pako$lib$zlib$inflate$$BAD;
            break;
          }
          state.offset = here_val;
          state.extra = (here_op) & 15;
          state.mode = $$$vendor$pako$lib$zlib$inflate$$DISTEXT;
          /* falls through */
        case $$$vendor$pako$lib$zlib$inflate$$DISTEXT:
          if (state.extra) {
            //=== NEEDBITS(state.extra);
            n = state.extra;
            while (bits < n) {
              if (have === 0) { break inf_leave; }
              have--;
              hold += input[next++] << bits;
              bits += 8;
            }
            //===//
            state.offset += hold & ((1 << state.extra) - 1)/*BITS(state.extra)*/;
            //--- DROPBITS(state.extra) ---//
            hold >>>= state.extra;
            bits -= state.extra;
            //---//
            state.back += state.extra;
          }
    //#ifdef INFLATE_STRICT
          if (state.offset > state.dmax) {
            strm.msg = 'invalid distance too far back';
            state.mode = $$$vendor$pako$lib$zlib$inflate$$BAD;
            break;
          }
    //#endif
          //Tracevv((stderr, "inflate:         distance %u\n", state.offset));
          state.mode = $$$vendor$pako$lib$zlib$inflate$$MATCH;
          /* falls through */
        case $$$vendor$pako$lib$zlib$inflate$$MATCH:
          if (left === 0) { break inf_leave; }
          copy = _out - left;
          if (state.offset > copy) {         /* copy from window */
            copy = state.offset - copy;
            if (copy > state.whave) {
              if (state.sane) {
                strm.msg = 'invalid distance too far back';
                state.mode = $$$vendor$pako$lib$zlib$inflate$$BAD;
                break;
              }
    // (!) This block is disabled in zlib defailts,
    // don't enable it for binary compatibility
    //#ifdef INFLATE_ALLOW_INVALID_DISTANCE_TOOFAR_ARRR
    //          Trace((stderr, "inflate.c too far\n"));
    //          copy -= state.whave;
    //          if (copy > state.length) { copy = state.length; }
    //          if (copy > left) { copy = left; }
    //          left -= copy;
    //          state.length -= copy;
    //          do {
    //            output[put++] = 0;
    //          } while (--copy);
    //          if (state.length === 0) { state.mode = LEN; }
    //          break;
    //#endif
            }
            if (copy > state.wnext) {
              copy -= state.wnext;
              from = state.wsize - copy;
            }
            else {
              from = state.wnext - copy;
            }
            if (copy > state.length) { copy = state.length; }
            from_source = state.window;
          }
          else {                              /* copy from output */
            from_source = output;
            from = put - state.offset;
            copy = state.length;
          }
          if (copy > left) { copy = left; }
          left -= copy;
          state.length -= copy;
          do {
            output[put++] = from_source[from++];
          } while (--copy);
          if (state.length === 0) { state.mode = $$$vendor$pako$lib$zlib$inflate$$LEN; }
          break;
        case $$$vendor$pako$lib$zlib$inflate$$LIT:
          if (left === 0) { break inf_leave; }
          output[put++] = state.length;
          left--;
          state.mode = $$$vendor$pako$lib$zlib$inflate$$LEN;
          break;
        case $$$vendor$pako$lib$zlib$inflate$$CHECK:
          if (state.wrap) {
            //=== NEEDBITS(32);
            while (bits < 32) {
              if (have === 0) { break inf_leave; }
              have--;
              // Use '|' insdead of '+' to make sure that result is signed
              hold |= input[next++] << bits;
              bits += 8;
            }
            //===//
            _out -= left;
            strm.total_out += _out;
            state.total += _out;
            if (_out) {
              strm.adler = state.check =
                  /*UPDATE(state.check, put - _out, _out);*/
                  (state.flags ? $$crc32$$default(state.check, output, _out, put - _out) : $$adler32$$default(state.check, output, _out, put - _out));

            }
            _out = left;
            // NB: crc32 stored as signed 32-bit int, zswap32 returns signed too
            if ((state.flags ? hold : $$$vendor$pako$lib$zlib$inflate$$zswap32(hold)) !== state.check) {
              strm.msg = 'incorrect data check';
              state.mode = $$$vendor$pako$lib$zlib$inflate$$BAD;
              break;
            }
            //=== INITBITS();
            hold = 0;
            bits = 0;
            //===//
            //Tracev((stderr, "inflate:   check matches trailer\n"));
          }
          state.mode = $$$vendor$pako$lib$zlib$inflate$$LENGTH;
          /* falls through */
        case $$$vendor$pako$lib$zlib$inflate$$LENGTH:
          if (state.wrap && state.flags) {
            //=== NEEDBITS(32);
            while (bits < 32) {
              if (have === 0) { break inf_leave; }
              have--;
              hold += input[next++] << bits;
              bits += 8;
            }
            //===//
            if (hold !== (state.total & 0xffffffff)) {
              strm.msg = 'incorrect length check';
              state.mode = $$$vendor$pako$lib$zlib$inflate$$BAD;
              break;
            }
            //=== INITBITS();
            hold = 0;
            bits = 0;
            //===//
            //Tracev((stderr, "inflate:   length matches trailer\n"));
          }
          state.mode = $$$vendor$pako$lib$zlib$inflate$$DONE;
          /* falls through */
        case $$$vendor$pako$lib$zlib$inflate$$DONE:
          ret = $$$vendor$pako$lib$zlib$inflate$$Z_STREAM_END;
          break inf_leave;
        case $$$vendor$pako$lib$zlib$inflate$$BAD:
          ret = $$$vendor$pako$lib$zlib$inflate$$Z_DATA_ERROR;
          break inf_leave;
        case $$$vendor$pako$lib$zlib$inflate$$MEM:
          return $$$vendor$pako$lib$zlib$inflate$$Z_MEM_ERROR;
        case $$$vendor$pako$lib$zlib$inflate$$SYNC:
          /* falls through */
        default:
          return $$$vendor$pako$lib$zlib$inflate$$Z_STREAM_ERROR;
        }
      }

      // inf_leave <- here is real place for "goto inf_leave", emulated via "break inf_leave"

      /*
         Return from inflate(), updating the total counts and the check value.
         If there was no progress during the inflate() call, return a buffer
         error.  Call updatewindow() to create and/or update the window state.
         Note: a memory error from inflate() is non-recoverable.
       */

      //--- RESTORE() ---
      strm.next_out = put;
      strm.avail_out = left;
      strm.next_in = next;
      strm.avail_in = have;
      state.hold = hold;
      state.bits = bits;
      //---

      if (state.wsize || (_out !== strm.avail_out && state.mode < $$$vendor$pako$lib$zlib$inflate$$BAD &&
                          (state.mode < $$$vendor$pako$lib$zlib$inflate$$CHECK || flush !== $$$vendor$pako$lib$zlib$inflate$$Z_FINISH))) {
        if ($$$vendor$pako$lib$zlib$inflate$$updatewindow(strm, strm.output, strm.next_out, _out - strm.avail_out)) {
          state.mode = $$$vendor$pako$lib$zlib$inflate$$MEM;
          return $$$vendor$pako$lib$zlib$inflate$$Z_MEM_ERROR;
        }
      }
      _in -= strm.avail_in;
      _out -= strm.avail_out;
      strm.total_in += _in;
      strm.total_out += _out;
      state.total += _out;
      if (state.wrap && _out) {
        strm.adler = state.check = /*UPDATE(state.check, strm.next_out - _out, _out);*/
          (state.flags ? $$crc32$$default(state.check, output, _out, strm.next_out - _out) : $$adler32$$default(state.check, output, _out, strm.next_out - _out));
      }
      strm.data_type = state.bits + (state.last ? 64 : 0) +
                        (state.mode === $$$vendor$pako$lib$zlib$inflate$$TYPE ? 128 : 0) +
                        (state.mode === $$$vendor$pako$lib$zlib$inflate$$LEN_ || state.mode === $$$vendor$pako$lib$zlib$inflate$$COPY_ ? 256 : 0);
      if (((_in === 0 && _out === 0) || flush === $$$vendor$pako$lib$zlib$inflate$$Z_FINISH) && ret === $$$vendor$pako$lib$zlib$inflate$$Z_OK) {
        ret = $$$vendor$pako$lib$zlib$inflate$$Z_BUF_ERROR;
      }
      return ret;
    }

    function $$$vendor$pako$lib$zlib$inflate$$inflateEnd(strm) {

      if (!strm || !strm.state /*|| strm->zfree == (free_func)0*/) {
        return $$$vendor$pako$lib$zlib$inflate$$Z_STREAM_ERROR;
      }

      var state = strm.state;
      if (state.window) {
        state.window = null;
      }
      strm.state = null;
      return $$$vendor$pako$lib$zlib$inflate$$Z_OK;
    }

    function $$$vendor$pako$lib$zlib$inflate$$inflateGetHeader(strm, head) {
      var state;

      /* check state */
      if (!strm || !strm.state) { return $$$vendor$pako$lib$zlib$inflate$$Z_STREAM_ERROR; }
      state = strm.state;
      if ((state.wrap & 2) === 0) { return $$$vendor$pako$lib$zlib$inflate$$Z_STREAM_ERROR; }

      /* save header structure */
      state.head = head;
      head.done = false;
      return $$$vendor$pako$lib$zlib$inflate$$Z_OK;
    }

    function $$$vendor$pako$lib$zlib$inflate$$inflateSetDictionary(strm, dictionary) {
      var dictLength = dictionary.length;

      var state;
      var dictid;
      var ret;

      /* check state */
      if (!strm /* == Z_NULL */ || !strm.state /* == Z_NULL */) { return $$$vendor$pako$lib$zlib$inflate$$Z_STREAM_ERROR; }
      state = strm.state;

      if (state.wrap !== 0 && state.mode !== $$$vendor$pako$lib$zlib$inflate$$DICT) {
        return $$$vendor$pako$lib$zlib$inflate$$Z_STREAM_ERROR;
      }

      /* check for correct dictionary identifier */
      if (state.mode === $$$vendor$pako$lib$zlib$inflate$$DICT) {
        dictid = 1; /* adler32(0, null, 0)*/
        /* dictid = adler32(dictid, dictionary, dictLength); */
        dictid = $$adler32$$default(dictid, dictionary, dictLength, 0);
        if (dictid !== state.check) {
          return $$$vendor$pako$lib$zlib$inflate$$Z_DATA_ERROR;
        }
      }
      /* copy dictionary to window using updatewindow(), which will amend the
       existing dictionary if appropriate */
      ret = $$$vendor$pako$lib$zlib$inflate$$updatewindow(strm, dictionary, dictLength, dictLength);
      if (ret) {
        state.mode = $$$vendor$pako$lib$zlib$inflate$$MEM;
        return $$$vendor$pako$lib$zlib$inflate$$Z_MEM_ERROR;
      }
      state.havedict = 1;
      // Tracev((stderr, "inflate:   dictionary set\n"));
      return $$$vendor$pako$lib$zlib$inflate$$Z_OK;
    }

    var $$$vendor$pako$lib$zlib$inflate$$inflateInfo = 'pako inflate (from Nodeca project)';

    function $$$vendor$pako$lib$zlib$zstream$$ZStream() {
      /* next input byte */
      this.input = null; // JS specific, because we have no pointers
      this.next_in = 0;
      /* number of bytes available at input */
      this.avail_in = 0;
      /* total number of input bytes read so far */
      this.total_in = 0;
      /* next output byte should be put there */
      this.output = null; // JS specific, because we have no pointers
      this.next_out = 0;
      /* remaining free space at output */
      this.avail_out = 0;
      /* total number of bytes output so far */
      this.total_out = 0;
      /* last error message, NULL if no error */
      this.msg = ''/*Z_NULL*/;
      /* not visible by applications */
      this.state = null;
      /* best guess about the data type: binary or text */
      this.data_type = 2/*Z_UNKNOWN*/;
      /* adler32 value of the uncompressed data */
      this.adler = 0;
    }

    var $$$vendor$pako$lib$zlib$zstream$$default = $$$vendor$pako$lib$zlib$zstream$$ZStream;

    class $$$inflator$$Inflate {
        constructor() {
            this.strm = new $$$vendor$pako$lib$zlib$zstream$$default();
            this.chunkSize = 1024 * 10 * 10;
            this.strm.output = new Uint8Array(this.chunkSize);
            this.windowBits = 5;

            $$$vendor$pako$lib$zlib$inflate$$inflateInit(this.strm, this.windowBits);
        }

        inflate(data, flush, expected) {
            this.strm.input = data;
            this.strm.avail_in = this.strm.input.length;
            this.strm.next_in = 0;
            this.strm.next_out = 0;

            // resize our output buffer if it's too small
            // (we could just use multiple chunks, but that would cause an extra
            // allocation each time to flatten the chunks)
            if (expected > this.chunkSize) {
                this.chunkSize = expected;
                this.strm.output = new Uint8Array(this.chunkSize);
            }

            this.strm.avail_out = this.chunkSize;

            $$$vendor$pako$lib$zlib$inflate$$inflate(this.strm, flush);

            return new Uint8Array(this.strm.output.buffer, 0, this.strm.next_out);
        }

        reset() {
            $$$vendor$pako$lib$zlib$inflate$$inflateReset(this.strm);
        }
    }

    var $$$inflator$$default = $$$inflator$$Inflate;

    class $$decoders$tight$$TightDecoder {
        constructor() {
            this._ctl = null;
            this._filter = null;
            this._numColors = 0;
            this._palette = new Uint8Array(1024);  // 256 * 4 (max palette size * max bytes-per-pixel)
            this._len = 0;

            this._zlibs = [];
            for (let i = 0; i < 4; i++) {
                this._zlibs[i] = new $$$inflator$$default();
            }
        }

        decodeRect(x, y, width, height, sock, display, depth) {
            if (this._ctl === null) {
                if (sock.rQwait("TIGHT compression-control", 1)) {
                    return false;
                }

                this._ctl = sock.rQshift8();

                // Reset streams if the server requests it
                for (let i = 0; i < 4; i++) {
                    if ((this._ctl >> i) & 1) {
                        this._zlibs[i].reset();
                        $$$core$util$logging$$.Info("Reset zlib stream " + i);
                    }
                }

                // Figure out filter
                this._ctl = this._ctl >> 4;
            }

            let ret;

            if (this._ctl === 0x08) {
                ret = this._fillRect(x, y, width, height,
                                     sock, display, depth);
            } else if (this._ctl === 0x09) {
                ret = this._jpegRect(x, y, width, height,
                                     sock, display, depth);
            } else if (this._ctl === 0x0A) {
                ret = this._pngRect(x, y, width, height,
                                    sock, display, depth);
            } else if ((this._ctl & 0x80) == 0) {
                ret = this._basicRect(this._ctl, x, y, width, height,
                                      sock, display, depth);
            } else {
                throw new Error("Illegal tight compression received (ctl: " +
                                       this._ctl + ")");
            }

            if (ret) {
                this._ctl = null;
            }

            return ret;
        }

        _fillRect(x, y, width, height, sock, display, depth) {
            if (sock.rQwait("TIGHT", 3)) {
                return false;
            }

            const rQi = sock.rQi;
            const rQ = sock.rQ;

            display.fillRect(x, y, width, height,
                             [rQ[rQi + 2], rQ[rQi + 1], rQ[rQi]], false);
            sock.rQskipBytes(3);

            return true;
        }

        _jpegRect(x, y, width, height, sock, display, depth) {
            let data = this._readData(sock);
            if (data === null) {
                return false;
            }

            display.imageRect(x, y, "image/jpeg", data);

            return true;
        }

        _pngRect(x, y, width, height, sock, display, depth) {
            throw new Error("PNG received in standard Tight rect");
        }

        _basicRect(ctl, x, y, width, height, sock, display, depth) {
            if (this._filter === null) {
                if (ctl & 0x4) {
                    if (sock.rQwait("TIGHT", 1)) {
                        return false;
                    }

                    this._filter = sock.rQshift8();
                } else {
                    // Implicit CopyFilter
                    this._filter = 0;
                }
            }

            let streamId = ctl & 0x3;

            let ret;

            switch (this._filter) {
                case 0: // CopyFilter
                    ret = this._copyFilter(streamId, x, y, width, height,
                                           sock, display, depth);
                    break;
                case 1: // PaletteFilter
                    ret = this._paletteFilter(streamId, x, y, width, height,
                                              sock, display, depth);
                    break;
                case 2: // GradientFilter
                    ret = this._gradientFilter(streamId, x, y, width, height,
                                               sock, display, depth);
                    break;
                default:
                    throw new Error("Illegal tight filter received (ctl: " +
                                           this._filter + ")");
            }

            if (ret) {
                this._filter = null;
            }

            return ret;
        }

        _copyFilter(streamId, x, y, width, height, sock, display, depth) {
            const uncompressedSize = width * height * 3;
            let data;

            if (uncompressedSize < 12) {
                if (sock.rQwait("TIGHT", uncompressedSize)) {
                    return false;
                }

                data = sock.rQshiftBytes(uncompressedSize);
            } else {
                data = this._readData(sock);
                if (data === null) {
                    return false;
                }

                data = this._zlibs[streamId].inflate(data, true, uncompressedSize);
                if (data.length != uncompressedSize) {
                    throw new Error("Incomplete zlib block");
                }
            }

            display.blitRgbImage(x, y, width, height, data, 0, false);

            return true;
        }

        _paletteFilter(streamId, x, y, width, height, sock, display, depth) {
            if (this._numColors === 0) {
                if (sock.rQwait("TIGHT palette", 1)) {
                    return false;
                }

                const numColors = sock.rQpeek8() + 1;
                const paletteSize = numColors * 3;

                if (sock.rQwait("TIGHT palette", 1 + paletteSize)) {
                    return false;
                }

                this._numColors = numColors;
                sock.rQskipBytes(1);

                sock.rQshiftTo(this._palette, paletteSize);
            }

            const bpp = (this._numColors <= 2) ? 1 : 8;
            const rowSize = Math.floor((width * bpp + 7) / 8);
            const uncompressedSize = rowSize * height;

            let data;

            if (uncompressedSize < 12) {
                if (sock.rQwait("TIGHT", uncompressedSize)) {
                    return false;
                }

                data = sock.rQshiftBytes(uncompressedSize);
            } else {
                data = this._readData(sock);
                if (data === null) {
                    return false;
                }

                data = this._zlibs[streamId].inflate(data, true, uncompressedSize);
                if (data.length != uncompressedSize) {
                    throw new Error("Incomplete zlib block");
                }
            }

            // Convert indexed (palette based) image data to RGB
            if (this._numColors == 2) {
                this._monoRect(x, y, width, height, data, this._palette, display);
            } else {
                this._paletteRect(x, y, width, height, data, this._palette, display);
            }

            this._numColors = 0;

            return true;
        }

        _monoRect(x, y, width, height, data, palette, display) {
            // Convert indexed (palette based) image data to RGB
            // TODO: reduce number of calculations inside loop
            const dest = this._getScratchBuffer(width * height * 4);
            const w = Math.floor((width + 7) / 8);
            const w1 = Math.floor(width / 8);

            for (let y = 0; y < height; y++) {
                let dp, sp, x;
                for (x = 0; x < w1; x++) {
                    for (let b = 7; b >= 0; b--) {
                        dp = (y * width + x * 8 + 7 - b) * 4;
                        sp = (data[y * w + x] >> b & 1) * 3;
                        dest[dp] = palette[sp];
                        dest[dp + 1] = palette[sp + 1];
                        dest[dp + 2] = palette[sp + 2];
                        dest[dp + 3] = 255;
                    }
                }

                for (let b = 7; b >= 8 - width % 8; b--) {
                    dp = (y * width + x * 8 + 7 - b) * 4;
                    sp = (data[y * w + x] >> b & 1) * 3;
                    dest[dp] = palette[sp];
                    dest[dp + 1] = palette[sp + 1];
                    dest[dp + 2] = palette[sp + 2];
                    dest[dp + 3] = 255;
                }
            }

            display.blitRgbxImage(x, y, width, height, dest, 0, false);
        }

        _paletteRect(x, y, width, height, data, palette, display) {
            // Convert indexed (palette based) image data to RGB
            const dest = this._getScratchBuffer(width * height * 4);
            const total = width * height * 4;
            for (let i = 0, j = 0; i < total; i += 4, j++) {
                const sp = data[j] * 3;
                dest[i] = palette[sp];
                dest[i + 1] = palette[sp + 1];
                dest[i + 2] = palette[sp + 2];
                dest[i + 3] = 255;
            }

            display.blitRgbxImage(x, y, width, height, dest, 0, false);
        }

        _gradientFilter(streamId, x, y, width, height, sock, display, depth) {
            throw new Error("Gradient filter not implemented");
        }

        _readData(sock) {
            if (this._len === 0) {
                if (sock.rQwait("TIGHT", 3)) {
                    return null;
                }

                let byte;

                byte = sock.rQshift8();
                this._len = byte & 0x7f;
                if (byte & 0x80) {
                    byte = sock.rQshift8();
                    this._len |= (byte & 0x7f) << 7;
                    if (byte & 0x80) {
                        byte = sock.rQshift8();
                        this._len |= byte << 14;
                    }
                }
            }

            if (sock.rQwait("TIGHT", this._len)) {
                return null;
            }

            let data = sock.rQshiftBytes(this._len);
            this._len = 0;

            return data;
        }

        _getScratchBuffer(size) {
            if (!this._scratchBuffer || (this._scratchBuffer.length < size)) {
                this._scratchBuffer = new Uint8Array(size);
            }
            return this._scratchBuffer;
        }
    }

    var $$decoders$tight$$default = $$decoders$tight$$TightDecoder;

    class $$decoders$tightpng$$TightPNGDecoder extends $$decoders$tight$$default {
        _pngRect(x, y, width, height, sock, display, depth) {
            let data = this._readData(sock);
            if (data === null) {
                return false;
            }

            display.imageRect(x, y, "image/png", data);

            return true;
        }

        _basicRect(ctl, x, y, width, height, sock, display, depth) {
            throw new Error("BasicCompression received in TightPNG rect");
        }
    }

    var $$decoders$tightpng$$default = $$decoders$tightpng$$TightPNGDecoder;

    // How many seconds to wait for a disconnect to finish
    const $$$core$rfb$$DISCONNECT_TIMEOUT = 3;
    const $$$core$rfb$$DEFAULT_BACKGROUND = 'rgb(40, 40, 40)';

    class $$$core$rfb$$RFB extends $$util$eventtarget$$default {
        constructor(target, url, options) {
            if (!target) {
                throw new Error("Must specify target");
            }
            if (!url) {
                throw new Error("Must specify URL");
            }

            super();

            this._target = target;
            this._url = url;

            // Connection details
            options = options || {};
            this._rfb_credentials = options.credentials || {};
            this._shared = 'shared' in options ? !!options.shared : true;
            this._repeaterID = options.repeaterID || '';
            this._showDotCursor = options.showDotCursor || false;

            // Internal state
            this._rfb_connection_state = '';
            this._rfb_init_state = '';
            this._rfb_auth_scheme = -1;
            this._rfb_clean_disconnect = true;

            // Server capabilities
            this._rfb_version = 0;
            this._rfb_max_version = 3.8;
            this._rfb_tightvnc = false;
            this._rfb_xvp_ver = 0;

            this._fb_width = 0;
            this._fb_height = 0;

            this._fb_name = "";

            this._capabilities = { power: false };

            this._supportsFence = false;

            this._supportsContinuousUpdates = false;
            this._enabledContinuousUpdates = false;

            this._supportsSetDesktopSize = false;
            this._screen_id = 0;
            this._screen_flags = 0;

            this._qemuExtKeyEventSupported = false;

            // Internal objects
            this._sock = null;              // Websock object
            this._display = null;           // Display object
            this._flushing = false;         // Display flushing state
            this._keyboard = null;          // Keyboard input handler object
            this._mouse = null;             // Mouse input handler object

            // Timers
            this._disconnTimer = null;      // disconnection timer
            this._resizeTimeout = null;     // resize rate limiting

            // Decoder states
            this._decoders = {};

            this._FBU = {
                rects: 0,
                x: 0,
                y: 0,
                width: 0,
                height: 0,
                encoding: null,
            };

            // Mouse state
            this._mouse_buttonMask = 0;
            this._mouse_arr = [];
            this._viewportDragging = false;
            this._viewportDragPos = {};
            this._viewportHasMoved = false;

            // Bound event handlers
            this._eventHandlers = {
                focusCanvas: this._focusCanvas.bind(this),
                windowResize: this._windowResize.bind(this),
            };

            // main setup
            $$$core$util$logging$$.Debug(">> RFB.constructor");

            // Create DOM elements
            this._screen = document.createElement('div');
            this._screen.style.display = 'flex';
            this._screen.style.width = '100%';
            this._screen.style.height = '100%';
            this._screen.style.overflow = 'auto';
            this._screen.style.background = $$$core$rfb$$DEFAULT_BACKGROUND;
            this._canvas = document.createElement('canvas');
            this._canvas.style.margin = 'auto';
            // Some browsers add an outline on focus
            this._canvas.style.outline = 'none';
            // IE miscalculates width without this :(
            this._canvas.style.flexShrink = '0';
            this._canvas.width = 0;
            this._canvas.height = 0;
            this._canvas.tabIndex = -1;
            this._screen.appendChild(this._canvas);

            // Cursor
            this._cursor = new $$util$cursor$$default();

            // XXX: TightVNC 2.8.11 sends no cursor at all until Windows changes
            // it. Result: no cursor at all until a window border or an edit field
            // is hit blindly. But there are also VNC servers that draw the cursor
            // in the framebuffer and don't send the empty local cursor. There is
            // no way to satisfy both sides.
            //
            // The spec is unclear on this "initial cursor" issue. Many other
            // viewers (TigerVNC, RealVNC, Remmina) display an arrow as the
            // initial cursor instead.
            this._cursorImage = $$$core$rfb$$RFB.cursors.none;

            // populate decoder array with objects
            this._decoders[$$encodings$$encodings.encodingRaw] = new $$decoders$raw$$default();
            this._decoders[$$encodings$$encodings.encodingCopyRect] = new $$decoders$copyrect$$default();
            this._decoders[$$encodings$$encodings.encodingRRE] = new $$decoders$rre$$default();
            this._decoders[$$encodings$$encodings.encodingHextile] = new $$decoders$hextile$$default();
            this._decoders[$$encodings$$encodings.encodingTight] = new $$decoders$tight$$default();
            this._decoders[$$encodings$$encodings.encodingTightPNG] = new $$decoders$tightpng$$default();

            // NB: nothing that needs explicit teardown should be done
            // before this point, since this can throw an exception
            try {
                this._display = new $$display$$default(this._canvas);
            } catch (exc) {
                $$$core$util$logging$$.Error("Display exception: " + exc);
                throw exc;
            }
            this._display.onflush = this._onFlush.bind(this);
            this._display.clear();

            this._keyboard = new $$$core$input$keyboard$$default(this._canvas);
            this._keyboard.onkeyevent = this._handleKeyEvent.bind(this);

            this._mouse = new $$input$mouse$$default(this._canvas);
            this._mouse.onmousebutton = this._handleMouseButton.bind(this);
            this._mouse.onmousemove = this._handleMouseMove.bind(this);

            this._sock = new $$websock$$default();
            this._sock.on('message', () => {
                this._handle_message();
            });
            this._sock.on('open', () => {
                if ((this._rfb_connection_state === 'connecting') &&
                    (this._rfb_init_state === '')) {
                    this._rfb_init_state = 'ProtocolVersion';
                    $$$core$util$logging$$.Debug("Starting VNC handshake");
                } else {
                    this._fail("Unexpected server connection while " +
                               this._rfb_connection_state);
                }
            });
            this._sock.on('close', (e) => {
                $$$core$util$logging$$.Debug("WebSocket on-close event");
                let msg = "";
                if (e.code) {
                    msg = "(code: " + e.code;
                    if (e.reason) {
                        msg += ", reason: " + e.reason;
                    }
                    msg += ")";
                }
                switch (this._rfb_connection_state) {
                    case 'connecting':
                        this._fail("Connection closed " + msg);
                        break;
                    case 'connected':
                        // Handle disconnects that were initiated server-side
                        this._updateConnectionState('disconnecting');
                        this._updateConnectionState('disconnected');
                        break;
                    case 'disconnecting':
                        // Normal disconnection path
                        this._updateConnectionState('disconnected');
                        break;
                    case 'disconnected':
                        this._fail("Unexpected server disconnect " +
                                   "when already disconnected " + msg);
                        break;
                    default:
                        this._fail("Unexpected server disconnect before connecting " +
                                   msg);
                        break;
                }
                this._sock.off('close');
            });
            this._sock.on('error', e => $$$core$util$logging$$.Warn("WebSocket on-error event"));

            // Slight delay of the actual connection so that the caller has
            // time to set up callbacks
            setTimeout(this._updateConnectionState.bind(this, 'connecting'));

            $$$core$util$logging$$.Debug("<< RFB.constructor");

            // ===== PROPERTIES =====

            this.dragViewport = false;
            this.focusOnClick = true;

            this._viewOnly = false;
            this._clipViewport = false;
            this._scaleViewport = false;
            this._resizeSession = false;
            this._localCursor = false;
        }

        // ===== PROPERTIES =====

        get viewOnly() { return this._viewOnly; }
        set viewOnly(viewOnly) {
            this._viewOnly = viewOnly;

            if (this._rfb_connection_state === "connecting" ||
                this._rfb_connection_state === "connected") {
                if (viewOnly) {
                    this._keyboard.ungrab();
                    this._mouse.ungrab();
                } else {
                    this._keyboard.grab();
                    this._mouse.grab();
                }
            }
        }

        get capabilities() { return this._capabilities; }

        get touchButton() { return this._mouse.touchButton; }
        set touchButton(button) { this._mouse.touchButton = button; }

        get clipViewport() { return this._clipViewport; }
        set clipViewport(viewport) {
            this._clipViewport = viewport;
            this._updateClip();
        }

        get scaleViewport() { return this._scaleViewport; }
        set scaleViewport(scale) {
            this._scaleViewport = scale;
            // Scaling trumps clipping, so we may need to adjust
            // clipping when enabling or disabling scaling
            if (scale && this._clipViewport) {
                this._updateClip();
            }
            this._updateScale();
            if (!scale && this._clipViewport) {
                this._updateClip();
            }
        }

        get resizeSession() { return this._resizeSession; }
        set resizeSession(resize) {
            this._resizeSession = resize;
            if (resize) {
                this._requestRemoteResize();
            }
        }

        get showDotCursor() { return this._showDotCursor; }
        set showDotCursor(show) {
            this._showDotCursor = show;
            this._refreshCursor();
        }

        get background() { return this._screen.style.background; }
        set background(cssValue) { this._screen.style.background = cssValue; }

        get localCursor() { return this._localCursor; }
        set localCursor(localCursor) {
            this._localCursor = localCursor;

            if (this._cursor) {
                this._cursor.setLocalCursor(localCursor);
            }
        }

        // ===== PUBLIC METHODS =====

        disconnect() {
            this._updateConnectionState('disconnecting');
            this._sock.off('error');
            this._sock.off('message');
            this._sock.off('open');
        }

        sendCredentials(creds) {
            this._rfb_credentials = creds;
            setTimeout(this._init_msg.bind(this), 0);
        }

        sendCtrlAltDel() {
            if (this._rfb_connection_state !== 'connected' || this._viewOnly) { return; }
            $$$core$util$logging$$.Info("Sending Ctrl-Alt-Del");

            this.sendKey($$$core$input$keysym$$default.XK_Control_L, "ControlLeft", true);
            this.sendKey($$$core$input$keysym$$default.XK_Alt_L, "AltLeft", true);
            this.sendKey($$$core$input$keysym$$default.XK_Delete, "Delete", true);
            this.sendKey($$$core$input$keysym$$default.XK_Delete, "Delete", false);
            this.sendKey($$$core$input$keysym$$default.XK_Alt_L, "AltLeft", false);
            this.sendKey($$$core$input$keysym$$default.XK_Control_L, "ControlLeft", false);
        }

        machineShutdown() {
            this._xvpOp(1, 2);
        }

        machineReboot() {
            this._xvpOp(1, 3);
        }

        machineReset() {
            this._xvpOp(1, 4);
        }

        // Send a key press. If 'down' is not specified then send a down key
        // followed by an up key.
        sendKey(keysym, code, down) {
            if (this._rfb_connection_state !== 'connected' || this._viewOnly) { return; }

            if (down === undefined) {
                this.sendKey(keysym, code, true);
                this.sendKey(keysym, code, false);
                return;
            }

            const scancode = $$input$xtscancodes$$default[code];

            if (this._qemuExtKeyEventSupported && scancode) {
                // 0 is NoSymbol
                keysym = keysym || 0;

                $$$core$util$logging$$.Info("Sending key (" + (down ? "down" : "up") + "): keysym " + keysym + ", scancode " + scancode);

                $$$core$rfb$$RFB.messages.QEMUExtendedKeyEvent(this._sock, keysym, down, scancode);
            } else {
                if (!keysym) {
                    return;
                }
                $$$core$util$logging$$.Info("Sending keysym (" + (down ? "down" : "up") + "): " + keysym);
                $$$core$rfb$$RFB.messages.keyEvent(this._sock, keysym, down ? 1 : 0);
            }
        }

        focus() {
            this._canvas.focus();
        }

        blur() {
            this._canvas.blur();
        }

        clipboardPasteFrom(text) {
            if (this._rfb_connection_state !== 'connected' || this._viewOnly) { return; }
            $$$core$rfb$$RFB.messages.clientCutText(this._sock, text);
        }

        // ===== PRIVATE METHODS =====

        _connect() {
            $$$core$util$logging$$.Debug(">> RFB.connect");

            $$$core$util$logging$$.Info("connecting to " + this._url);

            try {
                // WebSocket.onopen transitions to the RFB init states
                this._sock.open(this._url, ['binary']);
            } catch (e) {
                if (e.name === 'SyntaxError') {
                    this._fail("Invalid host or port (" + e + ")");
                } else {
                    this._fail("Error when opening socket (" + e + ")");
                }
            }

            // Make our elements part of the page
            this._target.appendChild(this._screen);

            this._cursor.attach(this._canvas);
            this._refreshCursor();

            // Monitor size changes of the screen
            // FIXME: Use ResizeObserver, or hidden overflow
            window.addEventListener('resize', this._eventHandlers.windowResize);

            // Always grab focus on some kind of click event
            this._canvas.addEventListener("mousedown", this._eventHandlers.focusCanvas);
            this._canvas.addEventListener("touchstart", this._eventHandlers.focusCanvas);

            $$$core$util$logging$$.Debug("<< RFB.connect");
        }

        _disconnect() {
            $$$core$util$logging$$.Debug(">> RFB.disconnect");
            this._cursor.detach();
            this._canvas.removeEventListener("mousedown", this._eventHandlers.focusCanvas);
            this._canvas.removeEventListener("touchstart", this._eventHandlers.focusCanvas);
            window.removeEventListener('resize', this._eventHandlers.windowResize);
            this._keyboard.ungrab();
            this._mouse.ungrab();
            this._sock.close();
            try {
                this._target.removeChild(this._screen);
            } catch (e) {
                if (e.name === 'NotFoundError') {
                    // Some cases where the initial connection fails
                    // can disconnect before the _screen is created
                } else {
                    throw e;
                }
            }
            clearTimeout(this._resizeTimeout);
            $$$core$util$logging$$.Debug("<< RFB.disconnect");
        }

        _focusCanvas(event) {
            // Respect earlier handlers' request to not do side-effects
            if (event.defaultPrevented) {
                return;
            }

            if (!this.focusOnClick) {
                return;
            }

            this.focus();
        }

        _windowResize(event) {
            // If the window resized then our screen element might have
            // as well. Update the viewport dimensions.
            window.requestAnimationFrame(() => {
                this._updateClip();
                this._updateScale();
            });

            if (this._resizeSession) {
                // Request changing the resolution of the remote display to
                // the size of the local browser viewport.

                // In order to not send multiple requests before the browser-resize
                // is finished we wait 0.5 seconds before sending the request.
                clearTimeout(this._resizeTimeout);
                this._resizeTimeout = setTimeout(this._requestRemoteResize.bind(this), 500);
            }
        }

        // Update state of clipping in Display object, and make sure the
        // configured viewport matches the current screen size
        _updateClip() {
            const cur_clip = this._display.clipViewport;
            let new_clip = this._clipViewport;

            if (this._scaleViewport) {
                // Disable viewport clipping if we are scaling
                new_clip = false;
            }

            if (cur_clip !== new_clip) {
                this._display.clipViewport = new_clip;
            }

            if (new_clip) {
                // When clipping is enabled, the screen is limited to
                // the size of the container.
                const size = this._screenSize();
                this._display.viewportChangeSize(size.w, size.h);
                this._fixScrollbars();
            }
        }

        _updateScale() {
            if (!this._scaleViewport) {
                this._display.scale = 1.0;
            } else {
                const size = this._screenSize();
                this._display.autoscale(size.w, size.h);
            }
            this._fixScrollbars();
        }

        // Requests a change of remote desktop size. This message is an extension
        // and may only be sent if we have received an ExtendedDesktopSize message
        _requestRemoteResize() {
            clearTimeout(this._resizeTimeout);
            this._resizeTimeout = null;

            if (!this._resizeSession || this._viewOnly ||
                !this._supportsSetDesktopSize) {
                return;
            }

            const size = this._screenSize();
            $$$core$rfb$$RFB.messages.setDesktopSize(this._sock,
                                        Math.floor(size.w), Math.floor(size.h),
                                        this._screen_id, this._screen_flags);

            $$$core$util$logging$$.Debug('Requested new desktop size: ' +
                       size.w + 'x' + size.h);
        }

        // Gets the the size of the available screen
        _screenSize() {
            let r = this._screen.getBoundingClientRect();
            return { w: r.width, h: r.height };
        }

        _fixScrollbars() {
            // This is a hack because Chrome screws up the calculation
            // for when scrollbars are needed. So to fix it we temporarily
            // toggle them off and on.
            const orig = this._screen.style.overflow;
            this._screen.style.overflow = 'hidden';
            // Force Chrome to recalculate the layout by asking for
            // an element's dimensions
            this._screen.getBoundingClientRect();
            this._screen.style.overflow = orig;
        }

        /*
         * Connection states:
         *   connecting
         *   connected
         *   disconnecting
         *   disconnected - permanent state
         */
        _updateConnectionState(state) {
            const oldstate = this._rfb_connection_state;

            if (state === oldstate) {
                $$$core$util$logging$$.Debug("Already in state '" + state + "', ignoring");
                return;
            }

            // The 'disconnected' state is permanent for each RFB object
            if (oldstate === 'disconnected') {
                $$$core$util$logging$$.Error("Tried changing state of a disconnected RFB object");
                return;
            }

            // Ensure proper transitions before doing anything
            switch (state) {
                case 'connected':
                    if (oldstate !== 'connecting') {
                        $$$core$util$logging$$.Error("Bad transition to connected state, " +
                                   "previous connection state: " + oldstate);
                        return;
                    }
                    break;

                case 'disconnected':
                    if (oldstate !== 'disconnecting') {
                        $$$core$util$logging$$.Error("Bad transition to disconnected state, " +
                                   "previous connection state: " + oldstate);
                        return;
                    }
                    break;

                case 'connecting':
                    if (oldstate !== '') {
                        $$$core$util$logging$$.Error("Bad transition to connecting state, " +
                                   "previous connection state: " + oldstate);
                        return;
                    }
                    break;

                case 'disconnecting':
                    if (oldstate !== 'connected' && oldstate !== 'connecting') {
                        $$$core$util$logging$$.Error("Bad transition to disconnecting state, " +
                                   "previous connection state: " + oldstate);
                        return;
                    }
                    break;

                default:
                    $$$core$util$logging$$.Error("Unknown connection state: " + state);
                    return;
            }

            // State change actions

            this._rfb_connection_state = state;

            $$$core$util$logging$$.Debug("New state '" + state + "', was '" + oldstate + "'.");

            if (this._disconnTimer && state !== 'disconnecting') {
                $$$core$util$logging$$.Debug("Clearing disconnect timer");
                clearTimeout(this._disconnTimer);
                this._disconnTimer = null;

                // make sure we don't get a double event
                this._sock.off('close');
            }

            switch (state) {
                case 'connecting':
                    this._connect();
                    break;

                case 'connected':
                    this.dispatchEvent(new CustomEvent("connect", { detail: {} }));
                    break;

                case 'disconnecting':
                    this._disconnect();

                    this._disconnTimer = setTimeout(() => {
                        $$$core$util$logging$$.Error("Disconnection timed out.");
                        this._updateConnectionState('disconnected');
                    }, $$$core$rfb$$DISCONNECT_TIMEOUT * 1000);
                    break;

                case 'disconnected':
                    this.dispatchEvent(new CustomEvent(
                        "disconnect", { detail:
                                        { clean: this._rfb_clean_disconnect } }));
                    break;
            }
        }

        /* Print errors and disconnect
         *
         * The parameter 'details' is used for information that
         * should be logged but not sent to the user interface.
         */
        _fail(details) {
            switch (this._rfb_connection_state) {
                case 'disconnecting':
                    $$$core$util$logging$$.Error("Failed when disconnecting: " + details);
                    break;
                case 'connected':
                    $$$core$util$logging$$.Error("Failed while connected: " + details);
                    break;
                case 'connecting':
                    $$$core$util$logging$$.Error("Failed when connecting: " + details);
                    break;
                default:
                    $$$core$util$logging$$.Error("RFB failure: " + details);
                    break;
            }
            this._rfb_clean_disconnect = false; //This is sent to the UI

            // Transition to disconnected without waiting for socket to close
            this._updateConnectionState('disconnecting');
            this._updateConnectionState('disconnected');

            return false;
        }

        _setCapability(cap, val) {
            this._capabilities[cap] = val;
            this.dispatchEvent(new CustomEvent("capabilities",
                                               { detail: { capabilities: this._capabilities } }));
        }

        _handle_message() {
            if (this._sock.rQlen === 0) {
                $$$core$util$logging$$.Warn("handle_message called on an empty receive queue");
                return;
            }

            switch (this._rfb_connection_state) {
                case 'disconnected':
                    $$$core$util$logging$$.Error("Got data while disconnected");
                    break;
                case 'connected':
                    while (true) {
                        if (this._flushing) {
                            break;
                        }
                        if (!this._normal_msg()) {
                            break;
                        }
                        if (this._sock.rQlen === 0) {
                            break;
                        }
                    }
                    break;
                default:
                    this._init_msg();
                    break;
            }
        }

        _handleKeyEvent(keysym, code, down) {
            this.sendKey(keysym, code, down);
        }

        _handleMouseButton(x, y, down, bmask) {
            if (down) {
                this._mouse_buttonMask |= bmask;
            } else {
                this._mouse_buttonMask &= ~bmask;
            }

            if (this.dragViewport) {
                if (down && !this._viewportDragging) {
                    this._viewportDragging = true;
                    this._viewportDragPos = {'x': x, 'y': y};
                    this._viewportHasMoved = false;

                    // Skip sending mouse events
                    return;
                } else {
                    this._viewportDragging = false;

                    // If we actually performed a drag then we are done
                    // here and should not send any mouse events
                    if (this._viewportHasMoved) {
                        return;
                    }

                    // Otherwise we treat this as a mouse click event.
                    // Send the button down event here, as the button up
                    // event is sent at the end of this function.
                    $$$core$rfb$$RFB.messages.pointerEvent(this._sock,
                                              this._display.absX(x),
                                              this._display.absY(y),
                                              bmask);
                }
            }

            if (this._viewOnly) { return; } // View only, skip mouse events

            if (this._rfb_connection_state !== 'connected') { return; }
            $$$core$rfb$$RFB.messages.pointerEvent(this._sock, this._display.absX(x), this._display.absY(y), this._mouse_buttonMask);
        }

        _handleMouseMove(x, y) {
            if (this._viewportDragging) {
                const deltaX = this._viewportDragPos.x - x;
                const deltaY = this._viewportDragPos.y - y;

                if (this._viewportHasMoved || (Math.abs(deltaX) > $$$core$util$browser$$dragThreshold ||
                                               Math.abs(deltaY) > $$$core$util$browser$$dragThreshold)) {
                    this._viewportHasMoved = true;

                    this._viewportDragPos = {'x': x, 'y': y};
                    this._display.viewportChangePos(deltaX, deltaY);
                }

                // Skip sending mouse events
                return;
            }

            if (this._viewOnly) { return; } // View only, skip mouse events

            if (this._rfb_connection_state !== 'connected') { return; }
            $$$core$rfb$$RFB.messages.pointerEvent(this._sock, this._display.absX(x), this._display.absY(y), this._mouse_buttonMask);
        }

        // Message Handlers

        _negotiate_protocol_version() {
            if (this._sock.rQwait("version", 12)) {
                return false;
            }

            const sversion = this._sock.rQshiftStr(12).substr(4, 7);
            $$$core$util$logging$$.Info("Server ProtocolVersion: " + sversion);
            let is_repeater = 0;
            switch (sversion) {
                case "000.000":  // UltraVNC repeater
                    is_repeater = 1;
                    break;
                case "003.003":
                case "003.006":  // UltraVNC
                case "003.889":  // Apple Remote Desktop
                    this._rfb_version = 3.3;
                    break;
                case "003.007":
                    this._rfb_version = 3.7;
                    break;
                case "003.008":
                case "004.000":  // Intel AMT KVM
                case "004.001":  // RealVNC 4.6
                case "005.000":  // RealVNC 5.3
                    this._rfb_version = 3.8;
                    break;
                default:
                    return this._fail("Invalid server version " + sversion);
            }

            if (is_repeater) {
                let repeaterID = "ID:" + this._repeaterID;
                while (repeaterID.length < 250) {
                    repeaterID += "\0";
                }
                this._sock.send_string(repeaterID);
                return true;
            }

            if (this._rfb_version > this._rfb_max_version) {
                this._rfb_version = this._rfb_max_version;
            }

            const cversion = "00" + parseInt(this._rfb_version, 10) +
                           ".00" + ((this._rfb_version * 10) % 10);
            this._sock.send_string("RFB " + cversion + "\n");
            $$$core$util$logging$$.Debug('Sent ProtocolVersion: ' + cversion);

            this._rfb_init_state = 'Security';
        }

        _negotiate_security() {
            // Polyfill since IE and PhantomJS doesn't have
            // TypedArray.includes()
            function includes(item, array) {
                for (let i = 0; i < array.length; i++) {
                    if (array[i] === item) {
                        return true;
                    }
                }
                return false;
            }

            if (this._rfb_version >= 3.7) {
                // Server sends supported list, client decides
                const num_types = this._sock.rQshift8();
                if (this._sock.rQwait("security type", num_types, 1)) { return false; }

                if (num_types === 0) {
                    this._rfb_init_state = "SecurityReason";
                    this._security_context = "no security types";
                    this._security_status = 1;
                    return this._init_msg();
                }

                const types = this._sock.rQshiftBytes(num_types);
                $$$core$util$logging$$.Debug("Server security types: " + types);

                // Look for each auth in preferred order
                if (includes(1, types)) {
                    this._rfb_auth_scheme = 1; // None
                } else if (includes(22, types)) {
                    this._rfb_auth_scheme = 22; // XVP
                } else if (includes(16, types)) {
                    this._rfb_auth_scheme = 16; // Tight
                } else if (includes(2, types)) {
                    this._rfb_auth_scheme = 2; // VNC Auth
                } else {
                    return this._fail("Unsupported security types (types: " + types + ")");
                }

                this._sock.send([this._rfb_auth_scheme]);
            } else {
                // Server decides
                if (this._sock.rQwait("security scheme", 4)) { return false; }
                this._rfb_auth_scheme = this._sock.rQshift32();

                if (this._rfb_auth_scheme == 0) {
                    this._rfb_init_state = "SecurityReason";
                    this._security_context = "authentication scheme";
                    this._security_status = 1;
                    return this._init_msg();
                }
            }

            this._rfb_init_state = 'Authentication';
            $$$core$util$logging$$.Debug('Authenticating using scheme: ' + this._rfb_auth_scheme);

            return this._init_msg(); // jump to authentication
        }

        _handle_security_reason() {
            if (this._sock.rQwait("reason length", 4)) {
                return false;
            }
            const strlen = this._sock.rQshift32();
            let reason = "";

            if (strlen > 0) {
                if (this._sock.rQwait("reason", strlen, 4)) { return false; }
                reason = this._sock.rQshiftStr(strlen);
            }

            if (reason !== "") {
                this.dispatchEvent(new CustomEvent(
                    "securityfailure",
                    { detail: { status: this._security_status,
                                reason: reason } }));

                return this._fail("Security negotiation failed on " +
                                  this._security_context +
                                  " (reason: " + reason + ")");
            } else {
                this.dispatchEvent(new CustomEvent(
                    "securityfailure",
                    { detail: { status: this._security_status } }));

                return this._fail("Security negotiation failed on " +
                                  this._security_context);
            }
        }

        // authentication
        _negotiate_xvp_auth() {
            if (!this._rfb_credentials.username ||
                !this._rfb_credentials.password ||
                !this._rfb_credentials.target) {
                this.dispatchEvent(new CustomEvent(
                    "credentialsrequired",
                    { detail: { types: ["username", "password", "target"] } }));
                return false;
            }

            const xvp_auth_str = String.fromCharCode(this._rfb_credentials.username.length) +
                               String.fromCharCode(this._rfb_credentials.target.length) +
                               this._rfb_credentials.username +
                               this._rfb_credentials.target;
            this._sock.send_string(xvp_auth_str);
            this._rfb_auth_scheme = 2;
            return this._negotiate_authentication();
        }

        _negotiate_std_vnc_auth() {
            if (this._sock.rQwait("auth challenge", 16)) { return false; }

            if (!this._rfb_credentials.password) {
                this.dispatchEvent(new CustomEvent(
                    "credentialsrequired",
                    { detail: { types: ["password"] } }));
                return false;
            }

            // TODO(directxman12): make genDES not require an Array
            const challenge = Array.prototype.slice.call(this._sock.rQshiftBytes(16));
            const response = $$$core$rfb$$RFB.genDES(this._rfb_credentials.password, challenge);
            this._sock.send(response);
            this._rfb_init_state = "SecurityResult";
            return true;
        }

        _negotiate_tight_tunnels(numTunnels) {
            const clientSupportedTunnelTypes = {
                0: { vendor: 'TGHT', signature: 'NOTUNNEL' }
            };
            const serverSupportedTunnelTypes = {};
            // receive tunnel capabilities
            for (let i = 0; i < numTunnels; i++) {
                const cap_code = this._sock.rQshift32();
                const cap_vendor = this._sock.rQshiftStr(4);
                const cap_signature = this._sock.rQshiftStr(8);
                serverSupportedTunnelTypes[cap_code] = { vendor: cap_vendor, signature: cap_signature };
            }

            $$$core$util$logging$$.Debug("Server Tight tunnel types: " + serverSupportedTunnelTypes);

            // Siemens touch panels have a VNC server that supports NOTUNNEL,
            // but forgets to advertise it. Try to detect such servers by
            // looking for their custom tunnel type.
            if (serverSupportedTunnelTypes[1] &&
                (serverSupportedTunnelTypes[1].vendor === "SICR") &&
                (serverSupportedTunnelTypes[1].signature === "SCHANNEL")) {
                $$$core$util$logging$$.Debug("Detected Siemens server. Assuming NOTUNNEL support.");
                serverSupportedTunnelTypes[0] = { vendor: 'TGHT', signature: 'NOTUNNEL' };
            }

            // choose the notunnel type
            if (serverSupportedTunnelTypes[0]) {
                if (serverSupportedTunnelTypes[0].vendor != clientSupportedTunnelTypes[0].vendor ||
                    serverSupportedTunnelTypes[0].signature != clientSupportedTunnelTypes[0].signature) {
                    return this._fail("Client's tunnel type had the incorrect " +
                                      "vendor or signature");
                }
                $$$core$util$logging$$.Debug("Selected tunnel type: " + clientSupportedTunnelTypes[0]);
                this._sock.send([0, 0, 0, 0]);  // use NOTUNNEL
                return false; // wait until we receive the sub auth count to continue
            } else {
                return this._fail("Server wanted tunnels, but doesn't support " +
                                  "the notunnel type");
            }
        }

        _negotiate_tight_auth() {
            if (!this._rfb_tightvnc) {  // first pass, do the tunnel negotiation
                if (this._sock.rQwait("num tunnels", 4)) { return false; }
                const numTunnels = this._sock.rQshift32();
                if (numTunnels > 0 && this._sock.rQwait("tunnel capabilities", 16 * numTunnels, 4)) { return false; }

                this._rfb_tightvnc = true;

                if (numTunnels > 0) {
                    this._negotiate_tight_tunnels(numTunnels);
                    return false;  // wait until we receive the sub auth to continue
                }
            }

            // second pass, do the sub-auth negotiation
            if (this._sock.rQwait("sub auth count", 4)) { return false; }
            const subAuthCount = this._sock.rQshift32();
            if (subAuthCount === 0) {  // empty sub-auth list received means 'no auth' subtype selected
                this._rfb_init_state = 'SecurityResult';
                return true;
            }

            if (this._sock.rQwait("sub auth capabilities", 16 * subAuthCount, 4)) { return false; }

            const clientSupportedTypes = {
                'STDVNOAUTH__': 1,
                'STDVVNCAUTH_': 2
            };

            const serverSupportedTypes = [];

            for (let i = 0; i < subAuthCount; i++) {
                this._sock.rQshift32(); // capNum
                const capabilities = this._sock.rQshiftStr(12);
                serverSupportedTypes.push(capabilities);
            }

            $$$core$util$logging$$.Debug("Server Tight authentication types: " + serverSupportedTypes);

            for (let authType in clientSupportedTypes) {
                if (serverSupportedTypes.indexOf(authType) != -1) {
                    this._sock.send([0, 0, 0, clientSupportedTypes[authType]]);
                    $$$core$util$logging$$.Debug("Selected authentication type: " + authType);

                    switch (authType) {
                        case 'STDVNOAUTH__':  // no auth
                            this._rfb_init_state = 'SecurityResult';
                            return true;
                        case 'STDVVNCAUTH_': // VNC auth
                            this._rfb_auth_scheme = 2;
                            return this._init_msg();
                        default:
                            return this._fail("Unsupported tiny auth scheme " +
                                              "(scheme: " + authType + ")");
                    }
                }
            }

            return this._fail("No supported sub-auth types!");
        }

        _negotiate_authentication() {
            switch (this._rfb_auth_scheme) {
                case 1:  // no auth
                    if (this._rfb_version >= 3.8) {
                        this._rfb_init_state = 'SecurityResult';
                        return true;
                    }
                    this._rfb_init_state = 'ClientInitialisation';
                    return this._init_msg();

                case 22:  // XVP auth
                    return this._negotiate_xvp_auth();

                case 2:  // VNC authentication
                    return this._negotiate_std_vnc_auth();

                case 16:  // TightVNC Security Type
                    return this._negotiate_tight_auth();

                default:
                    return this._fail("Unsupported auth scheme (scheme: " +
                                      this._rfb_auth_scheme + ")");
            }
        }

        _handle_security_result() {
            if (this._sock.rQwait('VNC auth response ', 4)) { return false; }

            const status = this._sock.rQshift32();

            if (status === 0) { // OK
                this._rfb_init_state = 'ClientInitialisation';
                $$$core$util$logging$$.Debug('Authentication OK');
                return this._init_msg();
            } else {
                if (this._rfb_version >= 3.8) {
                    this._rfb_init_state = "SecurityReason";
                    this._security_context = "security result";
                    this._security_status = status;
                    return this._init_msg();
                } else {
                    this.dispatchEvent(new CustomEvent(
                        "securityfailure",
                        { detail: { status: status } }));

                    return this._fail("Security handshake failed");
                }
            }
        }

        _negotiate_server_init() {
            if (this._sock.rQwait("server initialization", 24)) { return false; }

            /* Screen size */
            const width = this._sock.rQshift16();
            const height = this._sock.rQshift16();

            /* PIXEL_FORMAT */
            const bpp         = this._sock.rQshift8();
            const depth       = this._sock.rQshift8();
            const big_endian  = this._sock.rQshift8();
            const true_color  = this._sock.rQshift8();

            const red_max     = this._sock.rQshift16();
            const green_max   = this._sock.rQshift16();
            const blue_max    = this._sock.rQshift16();
            const red_shift   = this._sock.rQshift8();
            const green_shift = this._sock.rQshift8();
            const blue_shift  = this._sock.rQshift8();
            this._sock.rQskipBytes(3);  // padding

            // NB(directxman12): we don't want to call any callbacks or print messages until
            //                   *after* we're past the point where we could backtrack

            /* Connection name/title */
            const name_length = this._sock.rQshift32();
            if (this._sock.rQwait('server init name', name_length, 24)) { return false; }
            this._fb_name = $$util$strings$$decodeUTF8(this._sock.rQshiftStr(name_length));

            if (this._rfb_tightvnc) {
                if (this._sock.rQwait('TightVNC extended server init header', 8, 24 + name_length)) { return false; }
                // In TightVNC mode, ServerInit message is extended
                const numServerMessages = this._sock.rQshift16();
                const numClientMessages = this._sock.rQshift16();
                const numEncodings = this._sock.rQshift16();
                this._sock.rQskipBytes(2);  // padding

                const totalMessagesLength = (numServerMessages + numClientMessages + numEncodings) * 16;
                if (this._sock.rQwait('TightVNC extended server init header', totalMessagesLength, 32 + name_length)) { return false; }

                // we don't actually do anything with the capability information that TIGHT sends,
                // so we just skip the all of this.

                // TIGHT server message capabilities
                this._sock.rQskipBytes(16 * numServerMessages);

                // TIGHT client message capabilities
                this._sock.rQskipBytes(16 * numClientMessages);

                // TIGHT encoding capabilities
                this._sock.rQskipBytes(16 * numEncodings);
            }

            // NB(directxman12): these are down here so that we don't run them multiple times
            //                   if we backtrack
            $$$core$util$logging$$.Info("Screen: " + width + "x" + height +
                      ", bpp: " + bpp + ", depth: " + depth +
                      ", big_endian: " + big_endian +
                      ", true_color: " + true_color +
                      ", red_max: " + red_max +
                      ", green_max: " + green_max +
                      ", blue_max: " + blue_max +
                      ", red_shift: " + red_shift +
                      ", green_shift: " + green_shift +
                      ", blue_shift: " + blue_shift);

            if (big_endian !== 0) {
                $$$core$util$logging$$.Warn("Server native endian is not little endian");
            }

            if (red_shift !== 16) {
                $$$core$util$logging$$.Warn("Server native red-shift is not 16");
            }

            if (blue_shift !== 0) {
                $$$core$util$logging$$.Warn("Server native blue-shift is not 0");
            }

            // we're past the point where we could backtrack, so it's safe to call this
            this.dispatchEvent(new CustomEvent(
                "desktopname",
                { detail: { name: this._fb_name } }));

            this._resize(width, height);

            if (!this._viewOnly) { this._keyboard.grab(); }
            if (!this._viewOnly) { this._mouse.grab(); }

            this._fb_depth = 24;

            if (this._fb_name === "Intel(r) AMT KVM") {
                $$$core$util$logging$$.Warn("Intel AMT KVM only supports 8/16 bit depths. Using low color mode.");
                this._fb_depth = 8;
            }

            $$$core$rfb$$RFB.messages.pixelFormat(this._sock, this._fb_depth, true);
            this._sendEncodings();
            $$$core$rfb$$RFB.messages.fbUpdateRequest(this._sock, false, 0, 0, this._fb_width, this._fb_height);

            this._updateConnectionState('connected');
            return true;
        }

        _sendEncodings() {
            const encs = [];

            // In preference order
            encs.push($$encodings$$encodings.encodingCopyRect);
            // Only supported with full depth support
            if (this._fb_depth == 24) {
                encs.push($$encodings$$encodings.encodingTight);
                encs.push($$encodings$$encodings.encodingTightPNG);
                encs.push($$encodings$$encodings.encodingHextile);
                encs.push($$encodings$$encodings.encodingRRE);
            }
            encs.push($$encodings$$encodings.encodingRaw);

            // Psuedo-encoding settings
            encs.push($$encodings$$encodings.pseudoEncodingQualityLevel0 + 6);
            encs.push($$encodings$$encodings.pseudoEncodingCompressLevel0 + 2);

            encs.push($$encodings$$encodings.pseudoEncodingDesktopSize);
            encs.push($$encodings$$encodings.pseudoEncodingLastRect);
            encs.push($$encodings$$encodings.pseudoEncodingQEMUExtendedKeyEvent);
            encs.push($$encodings$$encodings.pseudoEncodingExtendedDesktopSize);
            encs.push($$encodings$$encodings.pseudoEncodingXvp);
            encs.push($$encodings$$encodings.pseudoEncodingFence);
            encs.push($$encodings$$encodings.pseudoEncodingContinuousUpdates);

            if (this._fb_depth == 24) {
                encs.push($$encodings$$encodings.pseudoEncodingCursor);
            }

            $$$core$rfb$$RFB.messages.clientEncodings(this._sock, encs);
        }

        /* RFB protocol initialization states:
         *   ProtocolVersion
         *   Security
         *   Authentication
         *   SecurityResult
         *   ClientInitialization - not triggered by server message
         *   ServerInitialization
         */
        _init_msg() {
            switch (this._rfb_init_state) {
                case 'ProtocolVersion':
                    return this._negotiate_protocol_version();

                case 'Security':
                    return this._negotiate_security();

                case 'Authentication':
                    return this._negotiate_authentication();

                case 'SecurityResult':
                    return this._handle_security_result();

                case 'SecurityReason':
                    return this._handle_security_reason();

                case 'ClientInitialisation':
                    this._sock.send([this._shared ? 1 : 0]); // ClientInitialisation
                    this._rfb_init_state = 'ServerInitialisation';
                    return true;

                case 'ServerInitialisation':
                    return this._negotiate_server_init();

                default:
                    return this._fail("Unknown init state (state: " +
                                      this._rfb_init_state + ")");
            }
        }

        _handle_set_colour_map_msg() {
            $$$core$util$logging$$.Debug("SetColorMapEntries");

            return this._fail("Unexpected SetColorMapEntries message");
        }

        _handle_server_cut_text() {
            $$$core$util$logging$$.Debug("ServerCutText");

            if (this._sock.rQwait("ServerCutText header", 7, 1)) { return false; }
            this._sock.rQskipBytes(3);  // Padding
            const length = this._sock.rQshift32();
            if (this._sock.rQwait("ServerCutText", length, 8)) { return false; }

            const text = this._sock.rQshiftStr(length);

            if (this._viewOnly) { return true; }

            this.dispatchEvent(new CustomEvent(
                "clipboard",
                { detail: { text: text } }));

            return true;
        }

        _handle_server_fence_msg() {
            if (this._sock.rQwait("ServerFence header", 8, 1)) { return false; }
            this._sock.rQskipBytes(3); // Padding
            let flags = this._sock.rQshift32();
            let length = this._sock.rQshift8();

            if (this._sock.rQwait("ServerFence payload", length, 9)) { return false; }

            if (length > 64) {
                $$$core$util$logging$$.Warn("Bad payload length (" + length + ") in fence response");
                length = 64;
            }

            const payload = this._sock.rQshiftStr(length);

            this._supportsFence = true;

            /*
             * Fence flags
             *
             *  (1<<0)  - BlockBefore
             *  (1<<1)  - BlockAfter
             *  (1<<2)  - SyncNext
             *  (1<<31) - Request
             */

            if (!(flags & (1<<31))) {
                return this._fail("Unexpected fence response");
            }

            // Filter out unsupported flags
            // FIXME: support syncNext
            flags &= (1<<0) | (1<<1);

            // BlockBefore and BlockAfter are automatically handled by
            // the fact that we process each incoming message
            // synchronuosly.
            $$$core$rfb$$RFB.messages.clientFence(this._sock, flags, payload);

            return true;
        }

        _handle_xvp_msg() {
            if (this._sock.rQwait("XVP version and message", 3, 1)) { return false; }
            this._sock.rQskipBytes(1);  // Padding
            const xvp_ver = this._sock.rQshift8();
            const xvp_msg = this._sock.rQshift8();

            switch (xvp_msg) {
                case 0:  // XVP_FAIL
                    $$$core$util$logging$$.Error("XVP Operation Failed");
                    break;
                case 1:  // XVP_INIT
                    this._rfb_xvp_ver = xvp_ver;
                    $$$core$util$logging$$.Info("XVP extensions enabled (version " + this._rfb_xvp_ver + ")");
                    this._setCapability("power", true);
                    break;
                default:
                    this._fail("Illegal server XVP message (msg: " + xvp_msg + ")");
                    break;
            }

            return true;
        }

        _normal_msg() {
            let msg_type;
            if (this._FBU.rects > 0) {
                msg_type = 0;
            } else {
                msg_type = this._sock.rQshift8();
            }

            let first, ret;
            switch (msg_type) {
                case 0:  // FramebufferUpdate
                    ret = this._framebufferUpdate();
                    if (ret && !this._enabledContinuousUpdates) {
                        $$$core$rfb$$RFB.messages.fbUpdateRequest(this._sock, true, 0, 0,
                                                     this._fb_width, this._fb_height);
                    }
                    return ret;

                case 1:  // SetColorMapEntries
                    return this._handle_set_colour_map_msg();

                case 2:  // Bell
                    $$$core$util$logging$$.Debug("Bell");
                    this.dispatchEvent(new CustomEvent(
                        "bell",
                        { detail: {} }));
                    return true;

                case 3:  // ServerCutText
                    return this._handle_server_cut_text();

                case 150: // EndOfContinuousUpdates
                    first = !this._supportsContinuousUpdates;
                    this._supportsContinuousUpdates = true;
                    this._enabledContinuousUpdates = false;
                    if (first) {
                        this._enabledContinuousUpdates = true;
                        this._updateContinuousUpdates();
                        $$$core$util$logging$$.Info("Enabling continuous updates.");
                    } else {
                        // FIXME: We need to send a framebufferupdaterequest here
                        // if we add support for turning off continuous updates
                    }
                    return true;

                case 248: // ServerFence
                    return this._handle_server_fence_msg();

                case 250:  // XVP
                    return this._handle_xvp_msg();

                default:
                    this._fail("Unexpected server message (type " + msg_type + ")");
                    $$$core$util$logging$$.Debug("sock.rQslice(0, 30): " + this._sock.rQslice(0, 30));
                    return true;
            }
        }

        _onFlush() {
            this._flushing = false;
            // Resume processing
            if (this._sock.rQlen > 0) {
                this._handle_message();
            }
        }

        _framebufferUpdate() {
            if (this._FBU.rects === 0) {
                if (this._sock.rQwait("FBU header", 3, 1)) { return false; }
                this._sock.rQskipBytes(1);  // Padding
                this._FBU.rects = this._sock.rQshift16();

                // Make sure the previous frame is fully rendered first
                // to avoid building up an excessive queue
                if (this._display.pending()) {
                    this._flushing = true;
                    this._display.flush();
                    return false;
                }
            }

            while (this._FBU.rects > 0) {
                if (this._FBU.encoding === null) {
                    if (this._sock.rQwait("rect header", 12)) { return false; }
                    /* New FramebufferUpdate */

                    const hdr = this._sock.rQshiftBytes(12);
                    this._FBU.x        = (hdr[0] << 8) + hdr[1];
                    this._FBU.y        = (hdr[2] << 8) + hdr[3];
                    this._FBU.width    = (hdr[4] << 8) + hdr[5];
                    this._FBU.height   = (hdr[6] << 8) + hdr[7];
                    this._FBU.encoding = parseInt((hdr[8] << 24) + (hdr[9] << 16) +
                                                  (hdr[10] << 8) + hdr[11], 10);
                }

                if (!this._handleRect()) {
                    return false;
                }

                this._FBU.rects--;
                this._FBU.encoding = null;
            }

            this._display.flip();

            return true;  // We finished this FBU
        }

        _handleRect() {
            switch (this._FBU.encoding) {
                case $$encodings$$encodings.pseudoEncodingLastRect:
                    this._FBU.rects = 1; // Will be decreased when we return
                    return true;

                case $$encodings$$encodings.pseudoEncodingCursor:
                    return this._handleCursor();

                case $$encodings$$encodings.pseudoEncodingQEMUExtendedKeyEvent:
                    // Old Safari doesn't support creating keyboard events
                    try {
                        const keyboardEvent = document.createEvent("keyboardEvent");
                        if (keyboardEvent.code !== undefined) {
                            this._qemuExtKeyEventSupported = true;
                        }
                    } catch (err) {
                        // Do nothing
                    }
                    return true;

                case $$encodings$$encodings.pseudoEncodingDesktopSize:
                    this._resize(this._FBU.width, this._FBU.height);
                    return true;

                case $$encodings$$encodings.pseudoEncodingExtendedDesktopSize:
                    return this._handleExtendedDesktopSize();

                default:
                    return this._handleDataRect();
            }
        }

        _handleCursor() {
            const hotx = this._FBU.x;  // hotspot-x
            const hoty = this._FBU.y;  // hotspot-y
            const w = this._FBU.width;
            const h = this._FBU.height;

            const pixelslength = w * h * 4;
            const masklength = Math.ceil(w / 8) * h;

            let bytes = pixelslength + masklength;
            if (this._sock.rQwait("cursor encoding", bytes)) {
                return false;
            }

            // Decode from BGRX pixels + bit mask to RGBA
            const pixels = this._sock.rQshiftBytes(pixelslength);
            const mask = this._sock.rQshiftBytes(masklength);
            let rgba = new Uint8Array(w * h * 4);

            let pix_idx = 0;
            for (let y = 0; y < h; y++) {
                for (let x = 0; x < w; x++) {
                    let mask_idx = y * Math.ceil(w / 8) + Math.floor(x / 8);
                    let alpha = (mask[mask_idx] << (x % 8)) & 0x80 ? 255 : 0;
                    rgba[pix_idx    ] = pixels[pix_idx + 2];
                    rgba[pix_idx + 1] = pixels[pix_idx + 1];
                    rgba[pix_idx + 2] = pixels[pix_idx];
                    rgba[pix_idx + 3] = alpha;
                    pix_idx += 4;
                }
            }

            this._updateCursor(rgba, hotx, hoty, w, h);

            return true;
        }

        _handleExtendedDesktopSize() {
            if (this._sock.rQwait("ExtendedDesktopSize", 4)) {
                return false;
            }

            const number_of_screens = this._sock.rQpeek8();

            let bytes = 4 + (number_of_screens * 16);
            if (this._sock.rQwait("ExtendedDesktopSize", bytes)) {
                return false;
            }

            const firstUpdate = !this._supportsSetDesktopSize;
            this._supportsSetDesktopSize = true;

            // Normally we only apply the current resize mode after a
            // window resize event. However there is no such trigger on the
            // initial connect. And we don't know if the server supports
            // resizing until we've gotten here.
            if (firstUpdate) {
                this._requestRemoteResize();
            }

            this._sock.rQskipBytes(1);  // number-of-screens
            this._sock.rQskipBytes(3);  // padding

            for (let i = 0; i < number_of_screens; i += 1) {
                // Save the id and flags of the first screen
                if (i === 0) {
                    this._screen_id = this._sock.rQshiftBytes(4);    // id
                    this._sock.rQskipBytes(2);                       // x-position
                    this._sock.rQskipBytes(2);                       // y-position
                    this._sock.rQskipBytes(2);                       // width
                    this._sock.rQskipBytes(2);                       // height
                    this._screen_flags = this._sock.rQshiftBytes(4); // flags
                } else {
                    this._sock.rQskipBytes(16);
                }
            }

            /*
             * The x-position indicates the reason for the change:
             *
             *  0 - server resized on its own
             *  1 - this client requested the resize
             *  2 - another client requested the resize
             */

            // We need to handle errors when we requested the resize.
            if (this._FBU.x === 1 && this._FBU.y !== 0) {
                let msg = "";
                // The y-position indicates the status code from the server
                switch (this._FBU.y) {
                    case 1:
                        msg = "Resize is administratively prohibited";
                        break;
                    case 2:
                        msg = "Out of resources";
                        break;
                    case 3:
                        msg = "Invalid screen layout";
                        break;
                    default:
                        msg = "Unknown reason";
                        break;
                }
                $$$core$util$logging$$.Warn("Server did not accept the resize request: "
                         + msg);
            } else {
                this._resize(this._FBU.width, this._FBU.height);
            }

            return true;
        }

        _handleDataRect() {
            let decoder = this._decoders[this._FBU.encoding];
            if (!decoder) {
                this._fail("Unsupported encoding (encoding: " +
                           this._FBU.encoding + ")");
                return false;
            }

            try {
                return decoder.decodeRect(this._FBU.x, this._FBU.y,
                                          this._FBU.width, this._FBU.height,
                                          this._sock, this._display,
                                          this._fb_depth);
            } catch (err) {
                this._fail("Error decoding rect: " + err);
                return false;
            }
        }

        _updateContinuousUpdates() {
            if (!this._enabledContinuousUpdates) { return; }

            $$$core$rfb$$RFB.messages.enableContinuousUpdates(this._sock, true, 0, 0,
                                                 this._fb_width, this._fb_height);
        }

        _resize(width, height) {
            this._fb_width = width;
            this._fb_height = height;

            this._display.resize(this._fb_width, this._fb_height);

            // Adjust the visible viewport based on the new dimensions
            this._updateClip();
            this._updateScale();

            // fbresize event
            var event = new CustomEvent("fbresize", {
                detail: {
                    rfb: this,
                    width: width,
                    height: height }
                }
            );
            this.dispatchEvent(event);

            this._updateContinuousUpdates();
        }

        _xvpOp(ver, op) {
            if (this._rfb_xvp_ver < ver) { return; }
            $$$core$util$logging$$.Info("Sending XVP operation " + op + " (version " + ver + ")");
            $$$core$rfb$$RFB.messages.xvpOp(this._sock, ver, op);
        }

        _updateCursor(rgba, hotx, hoty, w, h) {
            this._cursorImage = {
                rgbaPixels: rgba,
                hotx: hotx, hoty: hoty, w: w, h: h,
            };
            this._refreshCursor();
        }

        _shouldShowDotCursor() {
            // Called when this._cursorImage is updated
            if (!this._showDotCursor) {
                // User does not want to see the dot, so...
                return false;
            }

            // The dot should not be shown if the cursor is already visible,
            // i.e. contains at least one not-fully-transparent pixel.
            // So iterate through all alpha bytes in rgba and stop at the
            // first non-zero.
            for (let i = 3; i < this._cursorImage.rgbaPixels.length; i += 4) {
                if (this._cursorImage.rgbaPixels[i]) {
                    return false;
                }
            }

            // At this point, we know that the cursor is fully transparent, and
            // the user wants to see the dot instead of this.
            return true;
        }

        _refreshCursor() {
            const image = this._shouldShowDotCursor() ? $$$core$rfb$$RFB.cursors.dot : this._cursorImage;
            this._cursor.change(image.rgbaPixels,
                                image.hotx, image.hoty,
                                image.w, image.h
            );
        }

        static genDES(password, challenge) {
            const passwordChars = password.split('').map(c => c.charCodeAt(0));
            return (new $$des$$default(passwordChars)).encrypt(challenge);
        }
    }

    var $$$core$rfb$$default = $$$core$rfb$$RFB;

    // Class Methods
    $$$core$rfb$$RFB.messages = {
        keyEvent(sock, keysym, down) {
            const buff = sock._sQ;
            const offset = sock._sQlen;

            buff[offset] = 4;  // msg-type
            buff[offset + 1] = down;

            buff[offset + 2] = 0;
            buff[offset + 3] = 0;

            buff[offset + 4] = (keysym >> 24);
            buff[offset + 5] = (keysym >> 16);
            buff[offset + 6] = (keysym >> 8);
            buff[offset + 7] = keysym;

            sock._sQlen += 8;
            sock.flush();
        },

        QEMUExtendedKeyEvent(sock, keysym, down, keycode) {
            function getRFBkeycode(xt_scancode) {
                const upperByte = (keycode >> 8);
                const lowerByte = (keycode & 0x00ff);
                if (upperByte === 0xe0 && lowerByte < 0x7f) {
                    return lowerByte | 0x80;
                }
                return xt_scancode;
            }

            const buff = sock._sQ;
            const offset = sock._sQlen;

            buff[offset] = 255; // msg-type
            buff[offset + 1] = 0; // sub msg-type

            buff[offset + 2] = (down >> 8);
            buff[offset + 3] = down;

            buff[offset + 4] = (keysym >> 24);
            buff[offset + 5] = (keysym >> 16);
            buff[offset + 6] = (keysym >> 8);
            buff[offset + 7] = keysym;

            const RFBkeycode = getRFBkeycode(keycode);

            buff[offset + 8] = (RFBkeycode >> 24);
            buff[offset + 9] = (RFBkeycode >> 16);
            buff[offset + 10] = (RFBkeycode >> 8);
            buff[offset + 11] = RFBkeycode;

            sock._sQlen += 12;
            sock.flush();
        },

        pointerEvent(sock, x, y, mask) {
            const buff = sock._sQ;
            const offset = sock._sQlen;

            buff[offset] = 5; // msg-type

            buff[offset + 1] = mask;

            buff[offset + 2] = x >> 8;
            buff[offset + 3] = x;

            buff[offset + 4] = y >> 8;
            buff[offset + 5] = y;

            sock._sQlen += 6;
            sock.flush();
        },

        // TODO(directxman12): make this unicode compatible?
        clientCutText(sock, text) {
            const buff = sock._sQ;
            const offset = sock._sQlen;

            buff[offset] = 6; // msg-type

            buff[offset + 1] = 0; // padding
            buff[offset + 2] = 0; // padding
            buff[offset + 3] = 0; // padding

            let length = text.length;

            buff[offset + 4] = length >> 24;
            buff[offset + 5] = length >> 16;
            buff[offset + 6] = length >> 8;
            buff[offset + 7] = length;

            sock._sQlen += 8;

            // We have to keep track of from where in the text we begin creating the
            // buffer for the flush in the next iteration.
            let textOffset = 0;

            let remaining = length;
            while (remaining > 0) {

                let flushSize = Math.min(remaining, (sock._sQbufferSize - sock._sQlen));
                for (let i = 0; i < flushSize; i++) {
                    buff[sock._sQlen + i] =  text.charCodeAt(textOffset + i);
                }

                sock._sQlen += flushSize;
                sock.flush();

                remaining -= flushSize;
                textOffset += flushSize;
            }
        },

        setDesktopSize(sock, width, height, id, flags) {
            const buff = sock._sQ;
            const offset = sock._sQlen;

            buff[offset] = 251;              // msg-type
            buff[offset + 1] = 0;            // padding
            buff[offset + 2] = width >> 8;   // width
            buff[offset + 3] = width;
            buff[offset + 4] = height >> 8;  // height
            buff[offset + 5] = height;

            buff[offset + 6] = 1;            // number-of-screens
            buff[offset + 7] = 0;            // padding

            // screen array
            buff[offset + 8] = id >> 24;     // id
            buff[offset + 9] = id >> 16;
            buff[offset + 10] = id >> 8;
            buff[offset + 11] = id;
            buff[offset + 12] = 0;           // x-position
            buff[offset + 13] = 0;
            buff[offset + 14] = 0;           // y-position
            buff[offset + 15] = 0;
            buff[offset + 16] = width >> 8;  // width
            buff[offset + 17] = width;
            buff[offset + 18] = height >> 8; // height
            buff[offset + 19] = height;
            buff[offset + 20] = flags >> 24; // flags
            buff[offset + 21] = flags >> 16;
            buff[offset + 22] = flags >> 8;
            buff[offset + 23] = flags;

            sock._sQlen += 24;
            sock.flush();
        },

        clientFence(sock, flags, payload) {
            const buff = sock._sQ;
            const offset = sock._sQlen;

            buff[offset] = 248; // msg-type

            buff[offset + 1] = 0; // padding
            buff[offset + 2] = 0; // padding
            buff[offset + 3] = 0; // padding

            buff[offset + 4] = flags >> 24; // flags
            buff[offset + 5] = flags >> 16;
            buff[offset + 6] = flags >> 8;
            buff[offset + 7] = flags;

            const n = payload.length;

            buff[offset + 8] = n; // length

            for (let i = 0; i < n; i++) {
                buff[offset + 9 + i] = payload.charCodeAt(i);
            }

            sock._sQlen += 9 + n;
            sock.flush();
        },

        enableContinuousUpdates(sock, enable, x, y, width, height) {
            const buff = sock._sQ;
            const offset = sock._sQlen;

            buff[offset] = 150;             // msg-type
            buff[offset + 1] = enable;      // enable-flag

            buff[offset + 2] = x >> 8;      // x
            buff[offset + 3] = x;
            buff[offset + 4] = y >> 8;      // y
            buff[offset + 5] = y;
            buff[offset + 6] = width >> 8;  // width
            buff[offset + 7] = width;
            buff[offset + 8] = height >> 8; // height
            buff[offset + 9] = height;

            sock._sQlen += 10;
            sock.flush();
        },

        pixelFormat(sock, depth, true_color) {
            const buff = sock._sQ;
            const offset = sock._sQlen;

            let bpp;

            if (depth > 16) {
                bpp = 32;
            } else if (depth > 8) {
                bpp = 16;
            } else {
                bpp = 8;
            }

            const bits = Math.floor(depth/3);

            buff[offset] = 0;  // msg-type

            buff[offset + 1] = 0; // padding
            buff[offset + 2] = 0; // padding
            buff[offset + 3] = 0; // padding

            buff[offset + 4] = bpp;                 // bits-per-pixel
            buff[offset + 5] = depth;               // depth
            buff[offset + 6] = 0;                   // little-endian
            buff[offset + 7] = true_color ? 1 : 0;  // true-color

            buff[offset + 8] = 0;    // red-max
            buff[offset + 9] = (1 << bits) - 1;  // red-max

            buff[offset + 10] = 0;   // green-max
            buff[offset + 11] = (1 << bits) - 1; // green-max

            buff[offset + 12] = 0;   // blue-max
            buff[offset + 13] = (1 << bits) - 1; // blue-max

            buff[offset + 14] = bits * 2; // red-shift
            buff[offset + 15] = bits * 1; // green-shift
            buff[offset + 16] = bits * 0; // blue-shift

            buff[offset + 17] = 0;   // padding
            buff[offset + 18] = 0;   // padding
            buff[offset + 19] = 0;   // padding

            sock._sQlen += 20;
            sock.flush();
        },

        clientEncodings(sock, encodings) {
            const buff = sock._sQ;
            const offset = sock._sQlen;

            buff[offset] = 2; // msg-type
            buff[offset + 1] = 0; // padding

            buff[offset + 2] = encodings.length >> 8;
            buff[offset + 3] = encodings.length;

            let j = offset + 4;
            for (let i = 0; i < encodings.length; i++) {
                const enc = encodings[i];
                buff[j] = enc >> 24;
                buff[j + 1] = enc >> 16;
                buff[j + 2] = enc >> 8;
                buff[j + 3] = enc;

                j += 4;
            }

            sock._sQlen += j - offset;
            sock.flush();
        },

        fbUpdateRequest(sock, incremental, x, y, w, h) {
            const buff = sock._sQ;
            const offset = sock._sQlen;

            if (typeof(x) === "undefined") { x = 0; }
            if (typeof(y) === "undefined") { y = 0; }

            buff[offset] = 3;  // msg-type
            buff[offset + 1] = incremental ? 1 : 0;

            buff[offset + 2] = (x >> 8) & 0xFF;
            buff[offset + 3] = x & 0xFF;

            buff[offset + 4] = (y >> 8) & 0xFF;
            buff[offset + 5] = y & 0xFF;

            buff[offset + 6] = (w >> 8) & 0xFF;
            buff[offset + 7] = w & 0xFF;

            buff[offset + 8] = (h >> 8) & 0xFF;
            buff[offset + 9] = h & 0xFF;

            sock._sQlen += 10;
            sock.flush();
        },

        xvpOp(sock, ver, op) {
            const buff = sock._sQ;
            const offset = sock._sQlen;

            buff[offset] = 250; // msg-type
            buff[offset + 1] = 0; // padding

            buff[offset + 2] = ver;
            buff[offset + 3] = op;

            sock._sQlen += 4;
            sock.flush();
        }
    };

    $$$core$rfb$$RFB.cursors = {
        none: {
            rgbaPixels: new Uint8Array(),
            w: 0, h: 0,
            hotx: 0, hoty: 0,
        },

        dot: {
            /* eslint-disable indent */
            rgbaPixels: new Uint8Array([
                255, 255, 255, 255,   0,   0,   0, 255, 255, 255, 255, 255,
                  0,   0,   0, 255,   0,   0,   0,   0,   0,   0,  0,  255,
                255, 255, 255, 255,   0,   0,   0, 255, 255, 255, 255, 255,
            ]),
            /* eslint-enable indent */
            w: 3, h: 3,
            hotx: 1, hoty: 1,
        }
    };

    function $$webutil$$init_logging(level) {
        "use strict";
        if (typeof level !== "undefined") {
            $$$core$util$logging$$init_logging(level);
        } else {
            const param = document.location.href.match(/logging=([A-Za-z0-9._-]*)/);
            $$$core$util$logging$$init_logging(param || undefined);
        }
    }

    function $$webutil$$getQueryVar(name, defVal) {
        "use strict";
        const re = new RegExp('.*[?&]' + name + '=([^&#]*)'),
            match = document.location.href.match(re);
        if (typeof defVal === 'undefined') { defVal = null; }

        if (match) {
            return decodeURIComponent(match[1]);
        }

        return defVal;
    }

    function $$webutil$$getHashVar(name, defVal) {
        "use strict";
        const re = new RegExp('.*[&#]' + name + '=([^&]*)'),
            match = document.location.hash.match(re);
        if (typeof defVal === 'undefined') { defVal = null; }

        if (match) {
            return decodeURIComponent(match[1]);
        }

        return defVal;
    }

    function $$webutil$$getConfigVar(name, defVal) {
        "use strict";
        const val = $$webutil$$getHashVar(name);

        if (val === null) {
            return $$webutil$$getQueryVar(name, defVal);
        }

        return val;
    }

    function $$webutil$$createCookie(name, value, days) {
        "use strict";
        let date, expires;
        if (days) {
            date = new Date();
            date.setTime(date.getTime() + (days * 24 * 60 * 60 * 1000));
            expires = "; expires=" + date.toGMTString();
        } else {
            expires = "";
        }

        let secure;
        if (document.location.protocol === "https:") {
            secure = "; secure";
        } else {
            secure = "";
        }
        document.cookie = name + "=" + value + expires + "; path=/" + secure;
    }

    function $$webutil$$readCookie(name, defaultValue) {
        "use strict";
        const nameEQ = name + "=";
        const ca = document.cookie.split(';');

        for (let i = 0; i < ca.length; i += 1) {
            let c = ca[i];
            while (c.charAt(0) === ' ') {
                c = c.substring(1, c.length);
            }
            if (c.indexOf(nameEQ) === 0) {
                return c.substring(nameEQ.length, c.length);
            }
        }

        return (typeof defaultValue !== 'undefined') ? defaultValue : null;
    }

    function $$webutil$$eraseCookie(name) {
        "use strict";
        $$webutil$$createCookie(name, "", -1);
    }

    /*
     * Setting handling.
     */

    let $$webutil$$settings = {};

    function $$webutil$$initSettings() {
        if (!window.chrome || !window.chrome.storage) {
            $$webutil$$settings = {};
            return Promise.resolve();
        }

        return new Promise(resolve => window.chrome.storage.sync.get(resolve))
            .then((cfg) => { $$webutil$$settings = cfg; });
    }

    function $$webutil$$setSetting(name, value) {
        $$webutil$$settings[name] = value;
    }

    function $$webutil$$writeSetting(name, value) {
        "use strict";
        if ($$webutil$$settings[name] === value) return;
        $$webutil$$settings[name] = value;
        if (window.chrome && window.chrome.storage) {
            window.chrome.storage.sync.set($$webutil$$settings);
        } else {
            localStorage.setItem(name, value);
        }
    }

    function $$webutil$$readSetting(name, defaultValue) {
        "use strict";
        let value;
        if ((name in $$webutil$$settings) || (window.chrome && window.chrome.storage)) {
            value = $$webutil$$settings[name];
        } else {
            value = localStorage.getItem(name);
            $$webutil$$settings[name] = value;
        }
        if (typeof value === "undefined") {
            value = null;
        }

        if (value === null && typeof defaultValue !== "undefined") {
            return defaultValue;
        }

        return value;
    }

    function $$webutil$$eraseSetting(name) {
        "use strict";
        // Deleting here means that next time the setting is read when using local
        // storage, it will be pulled from local storage again.
        // If the setting in local storage is changed (e.g. in another tab)
        // between this delete and the next read, it could lead to an unexpected
        // value change.
        delete $$webutil$$settings[name];
        if (window.chrome && window.chrome.storage) {
            window.chrome.storage.sync.remove(name);
        } else {
            localStorage.removeItem(name);
        }
    }

    function $$webutil$$injectParamIfMissing(path, param, value) {
        // force pretend that we're dealing with a relative path
        // (assume that we wanted an extra if we pass one in)
        path = "/" + path;

        const elem = document.createElement('a');
        elem.href = path;

        const param_eq = encodeURIComponent(param) + "=";
        let query;
        if (elem.search) {
            query = elem.search.slice(1).split('&');
        } else {
            query = [];
        }

        if (!query.some(v => v.startsWith(param_eq))) {
            query.push(param_eq + encodeURIComponent(value));
            elem.search = "?" + query.join("&");
        }

        // some browsers (e.g. IE11) may occasionally omit the leading slash
        // in the elem.pathname string. Handle that case gracefully.
        if (elem.pathname.charAt(0) == "/") {
            return elem.pathname.slice(1) + elem.search + elem.hash;
        }

        return elem.pathname + elem.search + elem.hash;
    }

    function $$webutil$$fetchJSON(path) {
        return new Promise((resolve, reject) => {
            // NB: IE11 doesn't support JSON as a responseType
            const req = new XMLHttpRequest();
            req.open('GET', path);

            req.onload = () => {
                if (req.status === 200) {
                    let resObj;
                    try {
                        resObj = JSON.parse(req.responseText);
                    } catch (err) {
                        reject(err);
                    }
                    resolve(resObj);
                } else {
                    reject(new Error("XHR got non-200 status while trying to load '" + path + "': " + req.status));
                }
            };

            req.onerror = evt => reject(new Error("XHR encountered an error while trying to load '" + path + "': " + evt.message));

            req.ontimeout = evt => reject(new Error("XHR timed out while trying to load '" + path + "'"));

            req.send();
        });
    }

    function $$pve$$PVEUI(UI) {
        this.consoletype = $$webutil$$.getQueryVar('console');
        this.vmid = $$webutil$$.getQueryVar('vmid');
        this.vmname = $$webutil$$.getQueryVar('vmname');
        this.nodename = $$webutil$$.getQueryVar('node');
        this.resize = $$webutil$$.getQueryVar('resize');
        this.cmd = $$webutil$$.getQueryVar('cmd');
        this.lastFBWidth = undefined;
        this.lastFBHeight = undefined;
        this.sizeUpdateTimer = undefined;
        this.UI = UI;

        var baseUrl = '/nodes/' + this.nodename;
        var url;
        var params = { websocket: 1 };
        var title;

        switch (this.consoletype) {
        case 'kvm':
            baseUrl += '/qemu/' + this.vmid;
            url =  baseUrl + '/vncproxy';
            title = "VM " + this.vmid;
            if (this.vmname) {
            title += " ('" + this.vmname + "')";
            }
            break;
        case 'lxc':
            baseUrl += '/lxc/' + this.vmid;
            url =  baseUrl + '/vncproxy';
            title = "CT " + this.vmid;
            if (this.vmname) {
            title += " ('" + this.vmname + "')";
            }
            break;
        case 'shell':
            url =  baseUrl + '/vncshell';
            title = "node '" + this.nodename + "'";
            break;
        case 'upgrade':
            url =  baseUrl + '/vncshell';
            params.upgrade = 1;
            title = 'System upgrade on node ' + this.nodename;
            break;
        case 'cmd':
            url =  baseUrl + '/vncshell';
            params.cmd = decodeURI(this.cmd);
            title = 'Install Ceph on node ' + this.nodename;

            break;
        default:
            throw 'implement me';
            break;
        }

        if (this.resize == 'scale' &&
        (this.consoletype === 'lxc' || this.consoletype === 'shell')) {
        var size = this.getFBSize();
        params.width = size.width;
        params.height = size.height;
        }

        this.baseUrl = baseUrl;
        this.url = url;
        this.params = params;
        document.title = title;
    }

    var $$pve$$default = $$pve$$PVEUI;

    $$pve$$PVEUI.prototype = {
        urlEncode: function(object) {
        var i,value, params = [];

        for (i in object) {
            if (object.hasOwnProperty(i)) {
            value = object[i];
            if (value === undefined) value = '';
            params.push(encodeURIComponent(i) + '=' + encodeURIComponent(String(value)));
            }
        }

        return params.join('&');
        },

        API2Request: function(reqOpts) {
        var me = this;

        reqOpts.method = reqOpts.method || 'GET';

        var xhr = new XMLHttpRequest();

        xhr.onload = function() {
            var scope = reqOpts.scope || this;
            var result;
            var errmsg;

            if (xhr.readyState === 4) {
            var ctype = xhr.getResponseHeader('Content-Type');
            if (xhr.status === 200) {
                if (ctype.match(/application\/json;/)) {
                result = JSON.parse(xhr.responseText);
                } else {
                errmsg = 'got unexpected content type ' + ctype;
                }
            } else {
                errmsg = 'Error ' + xhr.status + ': ' + xhr.statusText;
            }
            } else {
            errmsg = 'Connection error - server offline?';
            }

            if (errmsg !== undefined) {
            if (reqOpts.failure) {
                reqOpts.failure.call(scope, errmsg);
            }
            } else {
            if (reqOpts.success) {
                reqOpts.success.call(scope, result);
            }
            }
            if (reqOpts.callback) {
            reqOpts.callback.call(scope, errmsg === undefined);
            }
        }

        var data = me.urlEncode(reqOpts.params || {});

        if (reqOpts.method === 'GET') {
            xhr.open(reqOpts.method, "/api2/json" + reqOpts.url + '?' + data);
        } else {
            xhr.open(reqOpts.method, "/api2/json" + reqOpts.url);
        }
        xhr.setRequestHeader('Cache-Control', 'no-cache');
        if (reqOpts.method === 'POST' || reqOpts.method === 'PUT') {
            xhr.setRequestHeader('Content-Type', 'application/x-www-form-urlencoded');
            xhr.setRequestHeader('CSRFPreventionToken', PVE.CSRFPreventionToken);
            xhr.send(data);
        } else if (reqOpts.method === 'GET') {
            xhr.send();
        } else {
            throw "unknown method";
        }
        },

        pve_detect_migrated_vm: function() {
        var me = this;
        if (me.consoletype === 'kvm') {
            // try to detect migrated VM
            me.API2Request({
            url: '/cluster/resources',
            method: 'GET',
            success: function(result) {
                var list = result.data;
                list.every(function(item) {
                if (item.type === 'qemu' && item.vmid == me.vmid) {
                    var url = "?" + me.urlEncode({
                    console: me.consoletype,
                    novnc: 1,
                    vmid: me.vmid,
                    vmname: me.vmname,
                    node: item.node,
                    resize: me.resize
                    });
                    location.href = url;
                    return false; // break
                }
                return true;
                });
            }
            });
        } else if(me.consoletype === 'lxc') {
            // lxc restart migration can take a while,
            // so we need to find out if we are really migrating
            var migrating;
            var check = setInterval(function() {
            if (migrating === undefined ||
                migrating === true) {
                // check (again) if migrating
                me.UI.showStatus('Waiting for connection...', 'warning', 5000);
                me.API2Request({
                url: me.baseUrl + '/config',
                method: 'GET',
                success: function(result) {
                    var lock = result.data.lock;
                    if (lock == 'migrate') {
                    migrating = true;
                    me.UI.showStatus('Migration detected, waiting...', 'warning', 5000);
                    } else {
                    migrating = false;
                    }
                },
                failure: function() {
                    migrating = false;
                }
                });
            } else {
                // not migrating any more
                me.UI.showStatus('Connection resumed', 'warning');
                clearInterval(check);
                me.API2Request({
                url: '/cluster/resources',
                method: 'GET',
                success: function(result) {
                    var list = result.data;
                    list.every(function(item) {
                    if (item.type === 'lxc' && item.vmid == me.vmid) {
                        var url = "?" + me.urlEncode({
                        console: me.consoletype,
                        novnc: 1,
                        vmid: me.vmid,
                        vmname: me.vmname,
                        node: item.node,
                        resize: me.resize
                        });
                        location.href = url;
                        return false; // break
                    }
                    return true;
                    });
                }
                });
            }
            }, 5000);
        }

        },

        pve_vm_command: function(cmd, params, reload) {
        var me = this;
        var baseUrl;
        var confirmMsg = "";

        switch(cmd) {
            case "start":
            reload = 1;
            case "shutdown":
            case "stop":
            case "reset":
            case "suspend":
            case "resume":
            confirmMsg = "Do you really want to " + cmd + " VM/CT {0}?";
            break;
            case "reload":
            location.reload();
            break;
            default:
            throw "implement me " + cmd;
        }

        confirmMsg = confirmMsg.replace('{0}', me.vmid);

        if (confirmMsg !== "" && confirm(confirmMsg) !== true) {
            return;
        }

        me.UI.closePVECommandPanel();

        if (me.consoletype === 'kvm') {
            baseUrl = '/nodes/' + me.nodename + '/qemu/' + me.vmid;
        } else if (me.consoletype === 'lxc') {
            baseUrl = '/nodes/' + me.nodename + '/lxc/' + me.vmid;
        } else {
            throw "unknown VM type";
        }

        me.API2Request({
            params: params,
            url: baseUrl + "/status/" + cmd,
            method: 'POST',
            failure: function(msg) {
            me.UI.showStatus(msg, 'warning');
            },
            success: function() {
            me.UI.showStatus("VM command '" + cmd +"' successful", 'normal');
            if (reload) {
                setTimeout(function() {
                location.reload();
                }, 1000);
            };
            }
        });
        },

        addPVEHandlers: function() {
        var me = this;
        document.getElementById('pve_commands_button')
            .addEventListener('click', me.UI.togglePVECommandPanel);

        // show/hide the buttons
        document.getElementById('noVNC_disconnect_button')
            .classList.add('noVNC_hidden');
        if (me.consoletype === 'kvm') {
            document.getElementById('noVNC_clipboard_button')
            .classList.add('noVNC_hidden');
        }

        if (me.consoletype === 'shell' || me.consoletype === 'upgrade') {
            document.getElementById('pve_commands_button')
            .classList.add('noVNC_hidden');
        }

        // add command logic
        var commandArray = [
            { cmd: 'start', kvm: 1, lxc: 1},
            { cmd: 'stop', kvm: 1, lxc: 1},
            { cmd: 'shutdown', kvm: 1, lxc: 1},
            { cmd: 'suspend', kvm: 1},
            { cmd: 'resume', kvm: 1},
            { cmd: 'reset', kvm: 1},
            { cmd: 'reload', kvm: 1, lxc: 1, shell: 1},
        ];

        commandArray.forEach(function(item) {
            var el = document.getElementById('pve_command_'+item.cmd);
            if (!el) {
            return;
            }

            if (item[me.consoletype] === 1) {
            el.onclick = function() {
                me.pve_vm_command(item.cmd);
            };
            } else {
            el.classList.add('noVNC_hidden');
            }
        });
        },

        getFBSize: function() {
        var oh;
        var ow;

        if (window.innerHeight) {
            oh = window.innerHeight;
            ow = window.innerWidth;
        } else if (document.documentElement &&
               document.documentElement.clientHeight) {
            oh = document.documentElement.clientHeight;
            ow = document.documentElement.clientWidth;
        } else if (document.body) {
            oh = document.body.clientHeight;
            ow = document.body.clientWidth;
        }  else {
            throw "can't get window size";
        }

        return { width: ow, height: oh };
        },

        pveStart: function(callback) {
        var me = this;
        me.API2Request({
            url: me.url,
            method: 'POST',
            params: me.params,
            success: function(result) {
            var wsparams = me.urlEncode({
                port: result.data.port,
                vncticket: result.data.ticket
            });

            document.getElementById('noVNC_password_input').value = result.data.ticket;
            me.UI.forceSetting('path', 'api2/json' + me.baseUrl + '/vncwebsocket' + "?" + wsparams);

            callback();
            },
            failure: function(msg) {
            me.UI.showStatus(msg, 'error');
            }
        });
        },

        updateFBSize: function(rfb, width, height) {
        var me = this;
        try {
            // Note: window size must be even number for firefox
            me.lastFBWidth = Math.floor((width + 1)/2)*2;
            me.lastFBHeight = Math.floor((height + 1)/2)*2;

            if (me.sizeUpdateTimer !== undefined) {
            clearInterval(me.sizeUpdateTimer);
            }

            var update_size = function() {
            var clip = me.UI.getSetting('view_clip');
            var resize = me.UI.getSetting('resize');
            var autoresize = me.UI.getSetting('autoresize');
            if (clip || resize === 'scale' || !autoresize) {
                return;
            }

            // we do not want to resize if we are in fullscreen
            if (document.fullscreenElement || // alternative standard method
                document.mozFullScreenElement || // currently working methods
                document.webkitFullscreenElement ||
                document.msFullscreenElement) {
                return;
            }

            var oldsize = me.getFBSize();
            var offsetw = me.lastFBWidth - oldsize.width;
            var offseth = me.lastFBHeight - oldsize.height;
            if (offsetw !== 0 || offseth !== 0) {
                //console.log("try resize by " + offsetw + " " + offseth);
                try {
                window.resizeBy(offsetw, offseth);
                } catch (e) {
                console.log('resizing did not work', e);
                }
            }
            };

            update_size();
            me.sizeUpdateTimer = setInterval(update_size, 1000);

        } catch(e) {
            console.log(e);
        }
        },
    };

    const app$ui$$UI = {

        connected: false,
        desktopName: "",

        statusTimeout: null,
        hideKeyboardTimeout: null,
        idleControlbarTimeout: null,
        closeControlbarTimeout: null,

        controlbarGrabbed: false,
        controlbarDrag: false,
        controlbarMouseDownClientY: 0,
        controlbarMouseDownOffsetY: 0,

        lastKeyboardinput: null,
        defaultKeyboardinputLen: 100,

        inhibit_reconnect: true,
        reconnect_callback: null,
        reconnect_password: null,

        prime() {
            return $$webutil$$.initSettings().then(() => {
                if (document.readyState === "interactive" || document.readyState === "complete") {
                    return app$ui$$UI.start();
                }

                return new Promise((resolve, reject) => {
                    document.addEventListener('DOMContentLoaded', () => app$ui$$UI.start().then(resolve).catch(reject));
                });
            });
        },

        // Render default UI and initialize settings menu
        start() {

            app$ui$$UI.PVE = new $$pve$$default(app$ui$$UI);

            app$ui$$UI.initSettings();

            // Translate the DOM
            $$localization$$l10n.translateDOM();

            // Adapt the interface for touch screen devices
            if ($$$core$util$browser$$isTouchDevice) {
                document.documentElement.classList.add("noVNC_touch");
                // Remove the address bar
                setTimeout(() => window.scrollTo(0, 1), 100);
            }

            // Restore control bar position
            if ($$webutil$$.readSetting('controlbar_pos') === 'right') {
                app$ui$$UI.toggleControlbarSide();
            }

            app$ui$$UI.initFullscreen();

            // Setup event handlers
            app$ui$$UI.addControlbarHandlers();
            app$ui$$UI.addTouchSpecificHandlers();
            app$ui$$UI.addExtraKeysHandlers();
            app$ui$$UI.addMachineHandlers();
            app$ui$$UI.addConnectionControlHandlers();
            app$ui$$UI.addClipboardHandlers();
            app$ui$$UI.addSettingsHandlers();

            // add pve specific event handlers
            app$ui$$UI.PVE.addPVEHandlers();
            document.getElementById("noVNC_status")
                .addEventListener('click', app$ui$$UI.hideStatus);

            // Bootstrap fallback input handler
            app$ui$$UI.keyboardinputReset();

            app$ui$$UI.openControlbar();

            app$ui$$UI.updateViewClip();

            app$ui$$UI.updateVisualState('init');

            document.documentElement.classList.remove("noVNC_loading");

            app$ui$$UI.PVE.pveStart(function() {
                app$ui$$UI.connect();
            });

            return Promise.resolve(app$ui$$UI.rfb);
        },

        initFullscreen() {
            // Only show the button if fullscreen is properly supported
            // * Safari doesn't support alphanumerical input while in fullscreen
            if (!$$$core$util$browser$$isSafari() &&
                (document.documentElement.requestFullscreen ||
                 document.documentElement.mozRequestFullScreen ||
                 document.documentElement.webkitRequestFullscreen ||
                 document.body.msRequestFullscreen)) {
                document.getElementById('noVNC_fullscreen_button')
                    .classList.remove("noVNC_hidden");
                app$ui$$UI.addFullscreenHandlers();
            }
        },

        initSettings() {
            // Logging selection dropdown
            const llevels = ['error', 'warn', 'info', 'debug'];
            for (let i = 0; i < llevels.length; i += 1) {
                app$ui$$UI.addOption(document.getElementById('noVNC_setting_logging'), llevels[i], llevels[i]);
            }

            // Settings with immediate effects
            app$ui$$UI.initSetting('logging', 'warn');
            app$ui$$UI.updateLogging();

            // if port == 80 (or 443) then it won't be present and should be
            // set manually
            let port = window.location.port;
            if (!port) {
                if (window.location.protocol.substring(0, 5) == 'https') {
                    port = 443;
                } else if (window.location.protocol.substring(0, 4) == 'http') {
                    port = 80;
                }
            }

            /* Populate the controls if defaults are provided in the URL */
            app$ui$$UI.initSetting('host', window.location.hostname);
            app$ui$$UI.initSetting('port', port);
            app$ui$$UI.initSetting('encrypt', true);
            app$ui$$UI.initSetting('view_clip', false);
            app$ui$$UI.initSetting('resize', 'off');
            app$ui$$UI.initSetting('autoresize', true);
            app$ui$$UI.initSetting('local_cursor', true);
            app$ui$$UI.initSetting('shared', true);
            app$ui$$UI.initSetting('view_only', false);
            app$ui$$UI.initSetting('show_dot', false);
            app$ui$$UI.initSetting('path', 'websockify');
            app$ui$$UI.initSetting('repeaterID', '');
            app$ui$$UI.initSetting('reconnect', false);
            app$ui$$UI.initSetting('reconnect_delay', 5000);

            app$ui$$UI.setupSettingLabels();
        },
        // Adds a link to the label elements on the corresponding input elements
        setupSettingLabels() {
            const labels = document.getElementsByTagName('LABEL');
            for (let i = 0; i < labels.length; i++) {
                const htmlFor = labels[i].htmlFor;
                if (htmlFor != '') {
                    const elem = document.getElementById(htmlFor);
                    if (elem) elem.label = labels[i];
                } else {
                    // If 'for' isn't set, use the first input element child
                    const children = labels[i].children;
                    for (let j = 0; j < children.length; j++) {
                        if (children[j].form !== undefined) {
                            children[j].label = labels[i];
                            break;
                        }
                    }
                }
            }
        },

    /* ------^-------
    *     /INIT
    * ==============
    * EVENT HANDLERS
    * ------v------*/

        addControlbarHandlers() {
            document.getElementById("noVNC_control_bar")
                .addEventListener('mousemove', app$ui$$UI.activateControlbar);
            document.getElementById("noVNC_control_bar")
                .addEventListener('mouseup', app$ui$$UI.activateControlbar);
            document.getElementById("noVNC_control_bar")
                .addEventListener('mousedown', app$ui$$UI.activateControlbar);
            document.getElementById("noVNC_control_bar")
                .addEventListener('keydown', app$ui$$UI.activateControlbar);

            document.getElementById("noVNC_control_bar")
                .addEventListener('mousedown', app$ui$$UI.keepControlbar);
            document.getElementById("noVNC_control_bar")
                .addEventListener('keydown', app$ui$$UI.keepControlbar);

            document.getElementById("noVNC_view_drag_button")
                .addEventListener('click', app$ui$$UI.toggleViewDrag);

            document.getElementById("noVNC_control_bar_handle")
                .addEventListener('mousedown', app$ui$$UI.controlbarHandleMouseDown);
            document.getElementById("noVNC_control_bar_handle")
                .addEventListener('mouseup', app$ui$$UI.controlbarHandleMouseUp);
            document.getElementById("noVNC_control_bar_handle")
                .addEventListener('mousemove', app$ui$$UI.dragControlbarHandle);
            // resize events aren't available for elements
            window.addEventListener('resize', app$ui$$UI.updateControlbarHandle);

            const exps = document.getElementsByClassName("noVNC_expander");
            for (let i = 0;i < exps.length;i++) {
                exps[i].addEventListener('click', app$ui$$UI.toggleExpander);
            }
        },

        addTouchSpecificHandlers() {
            document.getElementById("noVNC_mouse_button0")
                .addEventListener('click', () => app$ui$$UI.setMouseButton(1));
            document.getElementById("noVNC_mouse_button1")
                .addEventListener('click', () => app$ui$$UI.setMouseButton(2));
            document.getElementById("noVNC_mouse_button2")
                .addEventListener('click', () => app$ui$$UI.setMouseButton(4));
            document.getElementById("noVNC_mouse_button4")
                .addEventListener('click', () => app$ui$$UI.setMouseButton(0));
            document.getElementById("noVNC_keyboard_button")
                .addEventListener('click', app$ui$$UI.toggleVirtualKeyboard);

            app$ui$$UI.touchKeyboard = new $$$core$input$keyboard$$default(document.getElementById('noVNC_keyboardinput'));
            app$ui$$UI.touchKeyboard.onkeyevent = app$ui$$UI.keyEvent;
            app$ui$$UI.touchKeyboard.grab();
            document.getElementById("noVNC_keyboardinput")
                .addEventListener('input', app$ui$$UI.keyInput);
            document.getElementById("noVNC_keyboardinput")
                .addEventListener('focus', app$ui$$UI.onfocusVirtualKeyboard);
            document.getElementById("noVNC_keyboardinput")
                .addEventListener('blur', app$ui$$UI.onblurVirtualKeyboard);
            document.getElementById("noVNC_keyboardinput")
                .addEventListener('submit', () => false);

            document.documentElement
                .addEventListener('mousedown', app$ui$$UI.keepVirtualKeyboard, true);

            document.getElementById("noVNC_control_bar")
                .addEventListener('touchstart', app$ui$$UI.activateControlbar);
            document.getElementById("noVNC_control_bar")
                .addEventListener('touchmove', app$ui$$UI.activateControlbar);
            document.getElementById("noVNC_control_bar")
                .addEventListener('touchend', app$ui$$UI.activateControlbar);
            document.getElementById("noVNC_control_bar")
                .addEventListener('input', app$ui$$UI.activateControlbar);

            document.getElementById("noVNC_control_bar")
                .addEventListener('touchstart', app$ui$$UI.keepControlbar);
            document.getElementById("noVNC_control_bar")
                .addEventListener('input', app$ui$$UI.keepControlbar);

            document.getElementById("noVNC_control_bar_handle")
                .addEventListener('touchstart', app$ui$$UI.controlbarHandleMouseDown);
            document.getElementById("noVNC_control_bar_handle")
                .addEventListener('touchend', app$ui$$UI.controlbarHandleMouseUp);
            document.getElementById("noVNC_control_bar_handle")
                .addEventListener('touchmove', app$ui$$UI.dragControlbarHandle);
        },

        addExtraKeysHandlers() {
            document.getElementById("noVNC_toggle_extra_keys_button")
                .addEventListener('click', app$ui$$UI.toggleExtraKeys);
            document.getElementById("noVNC_toggle_ctrl_button")
                .addEventListener('click', app$ui$$UI.toggleCtrl);
            document.getElementById("noVNC_toggle_windows_button")
                .addEventListener('click', app$ui$$UI.toggleWindows);
            document.getElementById("noVNC_toggle_alt_button")
                .addEventListener('click', app$ui$$UI.toggleAlt);
            document.getElementById("noVNC_send_tab_button")
                .addEventListener('click', app$ui$$UI.sendTab);
            document.getElementById("noVNC_send_esc_button")
                .addEventListener('click', app$ui$$UI.sendEsc);
            document.getElementById("noVNC_send_ctrl_alt_del_button")
                .addEventListener('click', app$ui$$UI.sendCtrlAltDel);
        },

        addMachineHandlers() {
            document.getElementById("noVNC_shutdown_button")
                .addEventListener('click', () => app$ui$$UI.rfb.machineShutdown());
            document.getElementById("noVNC_reboot_button")
                .addEventListener('click', () => app$ui$$UI.rfb.machineReboot());
            document.getElementById("noVNC_reset_button")
                .addEventListener('click', () => app$ui$$UI.rfb.machineReset());
            document.getElementById("noVNC_power_button")
                .addEventListener('click', app$ui$$UI.togglePowerPanel);
        },

        addConnectionControlHandlers() {
            document.getElementById("noVNC_disconnect_button")
                .addEventListener('click', app$ui$$UI.disconnect);
            document.getElementById("noVNC_connect_button")
                .addEventListener('click', app$ui$$UI.connect);
            document.getElementById("noVNC_cancel_reconnect_button")
                .addEventListener('click', app$ui$$UI.cancelReconnect);

            document.getElementById("noVNC_password_button")
                .addEventListener('click', app$ui$$UI.setPassword);
        },

        addClipboardHandlers() {
            document.getElementById("noVNC_clipboard_button")
                .addEventListener('click', app$ui$$UI.toggleClipboardPanel);
            document.getElementById("noVNC_clipboard_text")
                .addEventListener('change', app$ui$$UI.clipboardSend);
            document.getElementById("noVNC_clipboard_clear_button")
                .addEventListener('click', app$ui$$UI.clipboardClear);
        },

        // Add a call to save settings when the element changes,
        // unless the optional parameter changeFunc is used instead.
        addSettingChangeHandler(name, changeFunc) {
            const settingElem = document.getElementById("noVNC_setting_" + name);
            if (changeFunc === undefined) {
                changeFunc = () => app$ui$$UI.saveSetting(name);
            }
            settingElem.addEventListener('change', changeFunc);
        },

        addSettingsHandlers() {
            document.getElementById("noVNC_settings_button")
                .addEventListener('click', app$ui$$UI.toggleSettingsPanel);

            app$ui$$UI.addSettingChangeHandler('encrypt');
            app$ui$$UI.addSettingChangeHandler('resize');
            app$ui$$UI.addSettingChangeHandler('resize', app$ui$$UI.applyResizeMode);
            app$ui$$UI.addSettingChangeHandler('resize', app$ui$$UI.updateViewClip);
            app$ui$$UI.addSettingChangeHandler('autoresize');
            app$ui$$UI.addSettingChangeHandler('view_clip');
            app$ui$$UI.addSettingChangeHandler('view_clip', app$ui$$UI.updateViewClip);
            app$ui$$UI.addSettingChangeHandler('shared');
            app$ui$$UI.addSettingChangeHandler('view_only');
            app$ui$$UI.addSettingChangeHandler('view_only', app$ui$$UI.updateViewOnly);
            app$ui$$UI.addSettingChangeHandler('show_dot');
            app$ui$$UI.addSettingChangeHandler('show_dot', app$ui$$UI.updateShowDotCursor);
            app$ui$$UI.addSettingChangeHandler('local_cursor');
            app$ui$$UI.addSettingChangeHandler('local_cursor', app$ui$$UI.updateLocalCursor);
            app$ui$$UI.addSettingChangeHandler('host');
            app$ui$$UI.addSettingChangeHandler('port');
            app$ui$$UI.addSettingChangeHandler('path');
            app$ui$$UI.addSettingChangeHandler('repeaterID');
            app$ui$$UI.addSettingChangeHandler('logging');
            app$ui$$UI.addSettingChangeHandler('logging', app$ui$$UI.updateLogging);
            app$ui$$UI.addSettingChangeHandler('reconnect');
            app$ui$$UI.addSettingChangeHandler('reconnect_delay');
        },

        addFullscreenHandlers() {
            document.getElementById("noVNC_fullscreen_button")
                .addEventListener('click', app$ui$$UI.toggleFullscreen);

            window.addEventListener('fullscreenchange', app$ui$$UI.updateFullscreenButton);
            window.addEventListener('mozfullscreenchange', app$ui$$UI.updateFullscreenButton);
            window.addEventListener('webkitfullscreenchange', app$ui$$UI.updateFullscreenButton);
            window.addEventListener('msfullscreenchange', app$ui$$UI.updateFullscreenButton);
        },

    /* ------^-------
     * /EVENT HANDLERS
     * ==============
     *     VISUAL
     * ------v------*/

        // Disable/enable controls depending on connection state
        updateVisualState(state) {

            document.documentElement.classList.remove("noVNC_connecting");
            document.documentElement.classList.remove("noVNC_connected");
            document.documentElement.classList.remove("noVNC_disconnecting");
            document.documentElement.classList.remove("noVNC_reconnecting");

            const transition_elem = document.getElementById("noVNC_transition_text");
            switch (state) {
                case 'init':
                    break;
                case 'connecting':
                    transition_elem.textContent = $$localization$$default("Connecting...");
                    document.documentElement.classList.add("noVNC_connecting");
                    break;
                case 'connected':
                    app$ui$$UI.connected = true;
                    app$ui$$UI.inhibit_reconnect = false;
                    app$ui$$UI.pveAllowMigratedTest = true;
                    document.documentElement.classList.add("noVNC_connected");
                    break;
                case 'disconnecting':
                    transition_elem.textContent = $$localization$$default("Disconnecting...");
                    document.documentElement.classList.add("noVNC_disconnecting");
                    break;
                case 'disconnected':
                    app$ui$$UI.showStatus($$localization$$default("Disconnected"));
                    if (app$ui$$UI.pveAllowMigratedTest === true) {
                        app$ui$$UI.pveAllowMigratedTest = false;
                        app$ui$$UI.PVE.pve_detect_migrated_vm();
                    }
                    break;
                case 'reconnecting':
                    transition_elem.textContent = $$localization$$default("Reconnecting...");
                    document.documentElement.classList.add("noVNC_reconnecting");
                    break;
                default:
                    $$$core$util$logging$$.Error("Invalid visual state: " + state);
                    app$ui$$UI.showStatus($$localization$$default("Internal error"), 'error');
                    return;
            }

            if (app$ui$$UI.connected) {
                app$ui$$UI.updateViewClip();

                app$ui$$UI.disableSetting('encrypt');
                app$ui$$UI.disableSetting('shared');
                app$ui$$UI.disableSetting('host');
                app$ui$$UI.disableSetting('port');
                app$ui$$UI.disableSetting('path');
                app$ui$$UI.disableSetting('repeaterID');
                app$ui$$UI.setMouseButton(1);

                // Hide the controlbar after 2 seconds
                app$ui$$UI.closeControlbarTimeout = setTimeout(app$ui$$UI.closeControlbar, 2000);
            } else {
                app$ui$$UI.enableSetting('encrypt');
                app$ui$$UI.enableSetting('shared');
                app$ui$$UI.enableSetting('host');
                app$ui$$UI.enableSetting('port');
                app$ui$$UI.enableSetting('path');
                app$ui$$UI.enableSetting('repeaterID');
                app$ui$$UI.updatePowerButton();
                app$ui$$UI.keepControlbar();
            }

            // State change closes the password dialog
            document.getElementById('noVNC_password_dlg')
                .classList.remove('noVNC_open');
        },

        showStatus(text, status_type, time) {
            const statusElem = document.getElementById('noVNC_status');

            clearTimeout(app$ui$$UI.statusTimeout);

            if (typeof status_type === 'undefined') {
                status_type = 'normal';
            }

            // Don't overwrite more severe visible statuses and never
            // errors. Only shows the first error.
            let visible_status_type = 'none';
            if (statusElem.classList.contains("noVNC_open")) {
                if (statusElem.classList.contains("noVNC_status_error")) {
                    visible_status_type = 'error';
                } else if (statusElem.classList.contains("noVNC_status_warn")) {
                    visible_status_type = 'warn';
                } else {
                    visible_status_type = 'normal';
                }
            }
            if (visible_status_type === 'error' ||
                (visible_status_type === 'warn' && status_type === 'normal')) {
                return;
            }

            switch (status_type) {
                case 'error':
                    statusElem.classList.remove("noVNC_status_warn");
                    statusElem.classList.remove("noVNC_status_normal");
                    statusElem.classList.add("noVNC_status_error");
                    break;
                case 'warning':
                case 'warn':
                    statusElem.classList.remove("noVNC_status_error");
                    statusElem.classList.remove("noVNC_status_normal");
                    statusElem.classList.add("noVNC_status_warn");
                    break;
                case 'normal':
                case 'info':
                default:
                    statusElem.classList.remove("noVNC_status_error");
                    statusElem.classList.remove("noVNC_status_warn");
                    statusElem.classList.add("noVNC_status_normal");
                    break;
            }

            statusElem.textContent = text;
            statusElem.classList.add("noVNC_open");

            // If no time was specified, show the status for 1.5 seconds
            if (typeof time === 'undefined') {
                time = 1500;
            }

            // Error messages do not timeout
            if (status_type !== 'error') {
                app$ui$$UI.statusTimeout = window.setTimeout(app$ui$$UI.hideStatus, time);
            }
        },

        hideStatus() {
            clearTimeout(app$ui$$UI.statusTimeout);
            document.getElementById('noVNC_status').classList.remove("noVNC_open");
        },

        activateControlbar(event) {
            clearTimeout(app$ui$$UI.idleControlbarTimeout);
            // We manipulate the anchor instead of the actual control
            // bar in order to avoid creating new a stacking group
            document.getElementById('noVNC_control_bar_anchor')
                .classList.remove("noVNC_idle");
            app$ui$$UI.idleControlbarTimeout = window.setTimeout(app$ui$$UI.idleControlbar, 2000);
        },

        idleControlbar() {
            document.getElementById('noVNC_control_bar_anchor')
                .classList.add("noVNC_idle");
        },

        keepControlbar() {
            clearTimeout(app$ui$$UI.closeControlbarTimeout);
        },

        openControlbar() {
            document.getElementById('noVNC_control_bar')
                .classList.add("noVNC_open");
        },

        closeControlbar() {
            app$ui$$UI.closeAllPanels();
            document.getElementById('noVNC_control_bar')
                .classList.remove("noVNC_open");
        },

        toggleControlbar() {
            if (document.getElementById('noVNC_control_bar')
                .classList.contains("noVNC_open")) {
                app$ui$$UI.closeControlbar();
            } else {
                app$ui$$UI.openControlbar();
            }
        },

        toggleControlbarSide() {
            // Temporarily disable animation, if bar is displayed, to avoid weird
            // movement. The transitionend-event will not fire when display=none.
            const bar = document.getElementById('noVNC_control_bar');
            const barDisplayStyle = window.getComputedStyle(bar).display;
            if (barDisplayStyle !== 'none') {
                bar.style.transitionDuration = '0s';
                bar.addEventListener('transitionend', () => bar.style.transitionDuration = '');
            }

            const anchor = document.getElementById('noVNC_control_bar_anchor');
            if (anchor.classList.contains("noVNC_right")) {
                $$webutil$$.writeSetting('controlbar_pos', 'left');
                anchor.classList.remove("noVNC_right");
            } else {
                $$webutil$$.writeSetting('controlbar_pos', 'right');
                anchor.classList.add("noVNC_right");
            }

            // Consider this a movement of the handle
            app$ui$$UI.controlbarDrag = true;
        },

        showControlbarHint(show) {
            const hint = document.getElementById('noVNC_control_bar_hint');
            if (show) {
                hint.classList.add("noVNC_active");
            } else {
                hint.classList.remove("noVNC_active");
            }
        },

        dragControlbarHandle(e) {
            if (!app$ui$$UI.controlbarGrabbed) return;

            const ptr = $$$core$util$events$$getPointerEvent(e);

            const anchor = document.getElementById('noVNC_control_bar_anchor');
            if (ptr.clientX < (window.innerWidth * 0.1)) {
                if (anchor.classList.contains("noVNC_right")) {
                    app$ui$$UI.toggleControlbarSide();
                }
            } else if (ptr.clientX > (window.innerWidth * 0.9)) {
                if (!anchor.classList.contains("noVNC_right")) {
                    app$ui$$UI.toggleControlbarSide();
                }
            }

            if (!app$ui$$UI.controlbarDrag) {
                const dragDistance = Math.abs(ptr.clientY - app$ui$$UI.controlbarMouseDownClientY);

                if (dragDistance < $$$core$util$browser$$dragThreshold) return;

                app$ui$$UI.controlbarDrag = true;
            }

            const eventY = ptr.clientY - app$ui$$UI.controlbarMouseDownOffsetY;

            app$ui$$UI.moveControlbarHandle(eventY);

            e.preventDefault();
            e.stopPropagation();
            app$ui$$UI.keepControlbar();
            app$ui$$UI.activateControlbar();
        },

        // Move the handle but don't allow any position outside the bounds
        moveControlbarHandle(viewportRelativeY) {
            const handle = document.getElementById("noVNC_control_bar_handle");
            const handleHeight = handle.getBoundingClientRect().height;
            const controlbarBounds = document.getElementById("noVNC_control_bar")
                .getBoundingClientRect();
            const margin = 10;

            // These heights need to be non-zero for the below logic to work
            if (handleHeight === 0 || controlbarBounds.height === 0) {
                return;
            }

            let newY = viewportRelativeY;

            // Check if the coordinates are outside the control bar
            if (newY < controlbarBounds.top + margin) {
                // Force coordinates to be below the top of the control bar
                newY = controlbarBounds.top + margin;

            } else if (newY > controlbarBounds.top +
                       controlbarBounds.height - handleHeight - margin) {
                // Force coordinates to be above the bottom of the control bar
                newY = controlbarBounds.top +
                    controlbarBounds.height - handleHeight - margin;
            }

            // Corner case: control bar too small for stable position
            if (controlbarBounds.height < (handleHeight + margin * 2)) {
                newY = controlbarBounds.top +
                    (controlbarBounds.height - handleHeight) / 2;
            }

            // The transform needs coordinates that are relative to the parent
            const parentRelativeY = newY - controlbarBounds.top;
            handle.style.transform = "translateY(" + parentRelativeY + "px)";
        },

        updateControlbarHandle() {
            // Since the control bar is fixed on the viewport and not the page,
            // the move function expects coordinates relative the the viewport.
            const handle = document.getElementById("noVNC_control_bar_handle");
            const handleBounds = handle.getBoundingClientRect();
            app$ui$$UI.moveControlbarHandle(handleBounds.top);
        },

        controlbarHandleMouseUp(e) {
            if ((e.type == "mouseup") && (e.button != 0)) return;

            // mouseup and mousedown on the same place toggles the controlbar
            if (app$ui$$UI.controlbarGrabbed && !app$ui$$UI.controlbarDrag) {
                app$ui$$UI.toggleControlbar();
                e.preventDefault();
                e.stopPropagation();
                app$ui$$UI.keepControlbar();
                app$ui$$UI.activateControlbar();
            }
            app$ui$$UI.controlbarGrabbed = false;
            app$ui$$UI.showControlbarHint(false);
        },

        controlbarHandleMouseDown(e) {
            if ((e.type == "mousedown") && (e.button != 0)) return;

            const ptr = $$$core$util$events$$getPointerEvent(e);

            const handle = document.getElementById("noVNC_control_bar_handle");
            const bounds = handle.getBoundingClientRect();

            // Touch events have implicit capture
            if (e.type === "mousedown") {
                $$$core$util$events$$setCapture(handle);
            }

            app$ui$$UI.controlbarGrabbed = true;
            app$ui$$UI.controlbarDrag = false;

            app$ui$$UI.showControlbarHint(true);

            app$ui$$UI.controlbarMouseDownClientY = ptr.clientY;
            app$ui$$UI.controlbarMouseDownOffsetY = ptr.clientY - bounds.top;
            e.preventDefault();
            e.stopPropagation();
            app$ui$$UI.keepControlbar();
            app$ui$$UI.activateControlbar();
        },

        toggleExpander(e) {
            if (this.classList.contains("noVNC_open")) {
                this.classList.remove("noVNC_open");
            } else {
                this.classList.add("noVNC_open");
            }
        },

    /* ------^-------
     *    /VISUAL
     * ==============
     *    SETTINGS
     * ------v------*/

        // Initial page load read/initialization of settings
        initSetting(name, defVal) {
            // Check Query string followed by cookie
            let val = $$webutil$$.getConfigVar(name);
            if (val === null) {
                val = $$webutil$$.readSetting(name, defVal);
            }
            $$webutil$$.setSetting(name, val);
            app$ui$$UI.updateSetting(name);
            return val;
        },

        // Set the new value, update and disable form control setting
        forceSetting(name, val) {
            $$webutil$$.setSetting(name, val);
            app$ui$$UI.updateSetting(name);
            app$ui$$UI.disableSetting(name);
        },

        // Update cookie and form control setting. If value is not set, then
        // updates from control to current cookie setting.
        updateSetting(name) {

            // Update the settings control
            let value = app$ui$$UI.getSetting(name);

            const ctrl = document.getElementById('noVNC_setting_' + name);
            if (ctrl.type === 'checkbox') {
                ctrl.checked = value;

            } else if (typeof ctrl.options !== 'undefined') {
                for (let i = 0; i < ctrl.options.length; i += 1) {
                    if (ctrl.options[i].value === value) {
                        ctrl.selectedIndex = i;
                        break;
                    }
                }
            } else {
                /*Weird IE9 error leads to 'null' appearring
                in textboxes instead of ''.*/
                if (value === null) {
                    value = "";
                }
                ctrl.value = value;
            }
        },

        // Save control setting to cookie
        saveSetting(name) {
            const ctrl = document.getElementById('noVNC_setting_' + name);
            let val;
            if (ctrl.type === 'checkbox') {
                val = ctrl.checked;
            } else if (typeof ctrl.options !== 'undefined') {
                val = ctrl.options[ctrl.selectedIndex].value;
            } else {
                val = ctrl.value;
            }
            $$webutil$$.writeSetting(name, val);
            //Log.Debug("Setting saved '" + name + "=" + val + "'");
            return val;
        },

        // Read form control compatible setting from cookie
        getSetting(name) {
            const ctrl = document.getElementById('noVNC_setting_' + name);
            let val = $$webutil$$.readSetting(name);
            if (typeof val !== 'undefined' && val !== null && ctrl.type === 'checkbox') {
                if (val.toString().toLowerCase() in {'0': 1, 'no': 1, 'false': 1}) {
                    val = false;
                } else {
                    val = true;
                }
            }
            return val;
        },

        // These helpers compensate for the lack of parent-selectors and
        // previous-sibling-selectors in CSS which are needed when we want to
        // disable the labels that belong to disabled input elements.
        disableSetting(name) {
            const ctrl = document.getElementById('noVNC_setting_' + name);
            ctrl.disabled = true;
            ctrl.label.classList.add('noVNC_disabled');
        },

        enableSetting(name) {
            const ctrl = document.getElementById('noVNC_setting_' + name);
            ctrl.disabled = false;
            ctrl.label.classList.remove('noVNC_disabled');
        },

    /* ------^-------
     *   /SETTINGS
     * ==============
     *    PANELS
     * ------v------*/

        closeAllPanels() {
            app$ui$$UI.closeSettingsPanel();
            app$ui$$UI.closePowerPanel();
            app$ui$$UI.closeClipboardPanel();
            app$ui$$UI.closeExtraKeys();
            app$ui$$UI.closePVECommandPanel();
        },

    /* ------^-------
     *   /PANELS
     * ==============
     * SETTINGS (panel)
     * ------v------*/

        openSettingsPanel() {
            app$ui$$UI.closeAllPanels();
            app$ui$$UI.openControlbar();

            // Refresh UI elements from saved cookies
            app$ui$$UI.updateSetting('encrypt');
            app$ui$$UI.updateSetting('view_clip');
            app$ui$$UI.updateSetting('resize');
            app$ui$$UI.updateSetting('shared');
            app$ui$$UI.updateSetting('view_only');
            app$ui$$UI.updateSetting('path');
            app$ui$$UI.updateSetting('repeaterID');
            app$ui$$UI.updateSetting('logging');
            app$ui$$UI.updateSetting('reconnect');
            app$ui$$UI.updateSetting('reconnect_delay');

            document.getElementById('noVNC_settings')
                .classList.add("noVNC_open");
            document.getElementById('noVNC_settings_button')
                .classList.add("noVNC_selected");
        },

        closeSettingsPanel() {
            document.getElementById('noVNC_settings')
                .classList.remove("noVNC_open");
            document.getElementById('noVNC_settings_button')
                .classList.remove("noVNC_selected");
        },

        toggleSettingsPanel() {
            if (document.getElementById('noVNC_settings')
                .classList.contains("noVNC_open")) {
                app$ui$$UI.closeSettingsPanel();
            } else {
                app$ui$$UI.openSettingsPanel();
            }
        },

    /* ------^-------
     *   /SETTINGS
     * ==============
     *     POWER
     * ------v------*/

        openPowerPanel() {
            app$ui$$UI.closeAllPanels();
            app$ui$$UI.openControlbar();

            document.getElementById('noVNC_power')
                .classList.add("noVNC_open");
            document.getElementById('noVNC_power_button')
                .classList.add("noVNC_selected");
        },

        closePowerPanel() {
            document.getElementById('noVNC_power')
                .classList.remove("noVNC_open");
            document.getElementById('noVNC_power_button')
                .classList.remove("noVNC_selected");
        },

        togglePowerPanel() {
            if (document.getElementById('noVNC_power')
                .classList.contains("noVNC_open")) {
                app$ui$$UI.closePowerPanel();
            } else {
                app$ui$$UI.openPowerPanel();
            }
        },

        // Disable/enable power button
        updatePowerButton() {
            if (app$ui$$UI.connected &&
                app$ui$$UI.rfb.capabilities.power &&
                !app$ui$$UI.rfb.viewOnly) {
                document.getElementById('noVNC_power_button')
                    .classList.remove("noVNC_hidden");
            } else {
                document.getElementById('noVNC_power_button')
                    .classList.add("noVNC_hidden");
                // Close power panel if open
                app$ui$$UI.closePowerPanel();
            }
        },

    /* ------^-------
     *    /POWER
     * ==============
     *   CLIPBOARD
     * ------v------*/

        openClipboardPanel() {
            app$ui$$UI.closeAllPanels();
            app$ui$$UI.openControlbar();

            document.getElementById('noVNC_clipboard')
                .classList.add("noVNC_open");
            document.getElementById('noVNC_clipboard_button')
                .classList.add("noVNC_selected");
        },

        closeClipboardPanel() {
            document.getElementById('noVNC_clipboard')
                .classList.remove("noVNC_open");
            document.getElementById('noVNC_clipboard_button')
                .classList.remove("noVNC_selected");
        },

        toggleClipboardPanel() {
            if (document.getElementById('noVNC_clipboard')
                .classList.contains("noVNC_open")) {
                app$ui$$UI.closeClipboardPanel();
            } else {
                app$ui$$UI.openClipboardPanel();
            }
        },

        clipboardReceive(e) {
            $$$core$util$logging$$.Debug(">> UI.clipboardReceive: " + e.detail.text.substr(0, 40) + "...");
            document.getElementById('noVNC_clipboard_text').value = e.detail.text;
            $$$core$util$logging$$.Debug("<< UI.clipboardReceive");
        },

        clipboardClear() {
            document.getElementById('noVNC_clipboard_text').value = "";
            app$ui$$UI.rfb.clipboardPasteFrom("");
        },

        clipboardSend() {
            const text = document.getElementById('noVNC_clipboard_text').value;
            $$$core$util$logging$$.Debug(">> UI.clipboardSend: " + text.substr(0, 40) + "...");
            app$ui$$UI.rfb.clipboardPasteFrom(text);
            $$$core$util$logging$$.Debug("<< UI.clipboardSend");
        },

    /* ------^-------
     *  /CLIPBOARD
     * ==============
     *  CONNECTION
     * ------v------*/

        openConnectPanel() {
            document.getElementById('noVNC_connect_dlg')
                .classList.add("noVNC_open");
        },

        closeConnectPanel() {
            document.getElementById('noVNC_connect_dlg')
                .classList.remove("noVNC_open");
        },

        connect(event, password) {

            // Ignore when rfb already exists
            if (typeof app$ui$$UI.rfb !== 'undefined') {
                return;
            }

            const host = app$ui$$UI.getSetting('host');
            const port = app$ui$$UI.getSetting('port');
            const path = app$ui$$UI.getSetting('path');

            if (typeof password === 'undefined') {
                password = $$webutil$$.getConfigVar('password');
                app$ui$$UI.reconnect_password = password;
            }

            var password = document.getElementById('noVNC_password_input').value;

            if (!password) {
                password = $$webutil$$.getConfigVar('password');
            }

            if (password === null) {
                password = undefined;
            }

            app$ui$$UI.hideStatus();

            if (!host) {
                $$$core$util$logging$$.Error("Can't connect when host is: " + host);
                app$ui$$UI.showStatus($$localization$$default("Must set host"), 'error');
                return;
            }

            app$ui$$UI.closeAllPanels();
            app$ui$$UI.closeConnectPanel();

            app$ui$$UI.updateVisualState('connecting');

            let url;

            url = app$ui$$UI.getSetting('encrypt') ? 'wss' : 'ws';

            url += '://' + host;
            if (port) {
                url += ':' + port;
            }
            url += '/' + path;

            app$ui$$UI.rfb = new $$$core$rfb$$default(document.getElementById('noVNC_container'), url,
                             { shared: app$ui$$UI.getSetting('shared'),
                               showDotCursor: app$ui$$UI.getSetting('show_dot'),
                               repeaterID: app$ui$$UI.getSetting('repeaterID'),
                               credentials: { password: password } });
            app$ui$$UI.rfb.addEventListener("connect", app$ui$$UI.connectFinished);
            app$ui$$UI.rfb.addEventListener("disconnect", app$ui$$UI.disconnectFinished);
            app$ui$$UI.rfb.addEventListener("credentialsrequired", app$ui$$UI.credentials);
            app$ui$$UI.rfb.addEventListener("securityfailure", app$ui$$UI.securityFailed);
            app$ui$$UI.rfb.addEventListener("capabilities", app$ui$$UI.updatePowerButton);
            app$ui$$UI.rfb.addEventListener("clipboard", app$ui$$UI.clipboardReceive);
            app$ui$$UI.rfb.addEventListener("bell", app$ui$$UI.bell);
            app$ui$$UI.rfb.addEventListener("desktopname", app$ui$$UI.updateDesktopName);
            app$ui$$UI.rfb.addEventListener("fbresize", app$ui$$UI.updateSessionSize);
            app$ui$$UI.rfb.clipViewport = app$ui$$UI.getSetting('view_clip');
            app$ui$$UI.rfb.localCursor = app$ui$$UI.getSetting('local_cursor');
            app$ui$$UI.rfb.scaleViewport = app$ui$$UI.getSetting('resize') === 'scale';
            app$ui$$UI.rfb.resizeSession = app$ui$$UI.getSetting('resize') === 'remote';

            app$ui$$UI.updateViewOnly(); // requires UI.rfb
        },

        disconnect() {
            app$ui$$UI.closeAllPanels();
            app$ui$$UI.rfb.disconnect();

            app$ui$$UI.connected = false;

            // Disable automatic reconnecting
            app$ui$$UI.inhibit_reconnect = true;

            app$ui$$UI.updateVisualState('disconnecting');

            // Don't display the connection settings until we're actually disconnected
        },

        reconnect() {
            app$ui$$UI.reconnect_callback = null;

            // if reconnect has been disabled in the meantime, do nothing.
            if (app$ui$$UI.inhibit_reconnect) {
                return;
            }

            app$ui$$UI.connect(null, app$ui$$UI.reconnect_password);
        },

        cancelReconnect() {
            if (app$ui$$UI.reconnect_callback !== null) {
                clearTimeout(app$ui$$UI.reconnect_callback);
                app$ui$$UI.reconnect_callback = null;
            }

            app$ui$$UI.updateVisualState('disconnected');

            app$ui$$UI.openControlbar();
            app$ui$$UI.openConnectPanel();
        },

        connectFinished(e) {
            app$ui$$UI.connected = true;
            app$ui$$UI.inhibit_reconnect = false;

            let msg;
            if (app$ui$$UI.getSetting('encrypt')) {
                msg = $$localization$$default("Connected (encrypted) to ") + app$ui$$UI.desktopName;
            } else {
                msg = $$localization$$default("Connected (unencrypted) to ") + app$ui$$UI.desktopName;
            }
            app$ui$$UI.showStatus(msg);
            app$ui$$UI.updateVisualState('connected');

            // Do this last because it can only be used on rendered elements
            app$ui$$UI.rfb.focus();
        },

        disconnectFinished(e) {
            const wasConnected = app$ui$$UI.connected;

            // This variable is ideally set when disconnection starts, but
            // when the disconnection isn't clean or if it is initiated by
            // the server, we need to do it here as well since
            // UI.disconnect() won't be used in those cases.
            app$ui$$UI.connected = false;

            app$ui$$UI.rfb = undefined;

            if (!e.detail.clean) {
                app$ui$$UI.updateVisualState('disconnected');
                if (wasConnected) {
                    app$ui$$UI.showStatus($$localization$$default("Something went wrong, connection is closed"),
                                  'error');
                } else {
                    app$ui$$UI.showStatus($$localization$$default("Failed to connect to server"), 'error');
                }
            } else if (app$ui$$UI.getSetting('reconnect', false) === true && !app$ui$$UI.inhibit_reconnect) {
                app$ui$$UI.updateVisualState('reconnecting');

                const delay = parseInt(app$ui$$UI.getSetting('reconnect_delay'));
                app$ui$$UI.reconnect_callback = setTimeout(app$ui$$UI.reconnect, delay);
                return;
            } else {
                app$ui$$UI.updateVisualState('disconnected');
                app$ui$$UI.showStatus($$localization$$default("Disconnected"), 'normal');
            }

            app$ui$$UI.openControlbar();
            app$ui$$UI.openConnectPanel();
        },

        securityFailed(e) {
            let msg = "";
            // On security failures we might get a string with a reason
            // directly from the server. Note that we can't control if
            // this string is translated or not.
            if ('reason' in e.detail) {
                msg = $$localization$$default("New connection has been rejected with reason: ") +
                    e.detail.reason;
            } else {
                msg = $$localization$$default("New connection has been rejected");
            }
            app$ui$$UI.showStatus(msg, 'error');
        },

    /* ------^-------
     *  /CONNECTION
     * ==============
     *   PASSWORD
     * ------v------*/

        credentials(e) {
            // FIXME: handle more types
            document.getElementById('noVNC_password_dlg')
                .classList.add('noVNC_open');

            setTimeout(() => document
                .getElementById('noVNC_password_input').focus(), 100);

            $$$core$util$logging$$.Warn("Server asked for a password");
            app$ui$$UI.showStatus($$localization$$default("Password is required"), "warning");
        },

        setPassword(e) {
            // Prevent actually submitting the form
            e.preventDefault();

            const inputElem = document.getElementById('noVNC_password_input');
            const password = inputElem.value;
            // Clear the input after reading the password
            inputElem.value = "";
            app$ui$$UI.rfb.sendCredentials({ password: password });
            app$ui$$UI.reconnect_password = password;
            document.getElementById('noVNC_password_dlg')
                .classList.remove('noVNC_open');
        },

    /* ------^-------
     *  /PASSWORD
     * ==============
     *   FULLSCREEN
     * ------v------*/

        toggleFullscreen() {
            if (document.fullscreenElement || // alternative standard method
                document.mozFullScreenElement || // currently working methods
                document.webkitFullscreenElement ||
                document.msFullscreenElement) {
                if (document.exitFullscreen) {
                    document.exitFullscreen();
                } else if (document.mozCancelFullScreen) {
                    document.mozCancelFullScreen();
                } else if (document.webkitExitFullscreen) {
                    document.webkitExitFullscreen();
                } else if (document.msExitFullscreen) {
                    document.msExitFullscreen();
                }

                // when changing from fullscreen to window,
                // re enable auto resize
                if ($$webutil$$.getQueryVar('resize') !== 'scale') {
                    app$ui$$UI.forceSetting('resize', 'off');
                    app$ui$$UI.enableSetting('resize');
                }
            } else {
                if (document.documentElement.requestFullscreen) {
                    document.documentElement.requestFullscreen();
                } else if (document.documentElement.mozRequestFullScreen) {
                    document.documentElement.mozRequestFullScreen();
                } else if (document.documentElement.webkitRequestFullscreen) {
                    document.documentElement.webkitRequestFullscreen(Element.ALLOW_KEYBOARD_INPUT);
                } else if (document.body.msRequestFullscreen) {
                    document.body.msRequestFullscreen();
                }
                // we want scaling in fullscreen mode
                app$ui$$UI.forceSetting('resize', 'scale');
                app$ui$$UI.enableSetting('resize');
            }
            app$ui$$UI.applyResizeMode();
            app$ui$$UI.updateFullscreenButton();
        },

        updateFullscreenButton() {
            if (document.fullscreenElement || // alternative standard method
                document.mozFullScreenElement || // currently working methods
                document.webkitFullscreenElement ||
                document.msFullscreenElement ) {
                document.getElementById('noVNC_fullscreen_button')
                    .classList.add("noVNC_selected");
            } else {
                document.getElementById('noVNC_fullscreen_button')
                    .classList.remove("noVNC_selected");
            }
        },

    /* ------^-------
     *  /FULLSCREEN
     * ==============
     *     RESIZE
     * ------v------*/

        // Apply remote resizing or local scaling
        applyResizeMode() {
            if (!app$ui$$UI.rfb) return;

            app$ui$$UI.rfb.scaleViewport = app$ui$$UI.getSetting('resize') === 'scale';
            app$ui$$UI.rfb.resizeSession = app$ui$$UI.getSetting('resize') === 'remote';
        },

    /* ------^-------
     *    /RESIZE
     * ==============
     * VIEW CLIPPING
     * ------v------*/

        // Update viewport clipping property for the connection. The normal
        // case is to get the value from the setting. There are special cases
        // for when the viewport is scaled or when a touch device is used.
        updateViewClip() {
            if (!app$ui$$UI.rfb) return;

            const scaling = app$ui$$UI.getSetting('resize') === 'scale';

            if (scaling) {
                // Can't be clipping if viewport is scaled to fit
                app$ui$$UI.forceSetting('view_clip', false);
                app$ui$$UI.rfb.clipViewport  = false;
            } else if ($$$core$util$browser$$isIOS() || $$$core$util$browser$$isAndroid()) {
                // iOS and Android usually have shit scrollbars
                app$ui$$UI.forceSetting('view_clip', true);
                app$ui$$UI.rfb.clipViewport = true;
            } else {
                app$ui$$UI.enableSetting('view_clip');
                app$ui$$UI.rfb.clipViewport = app$ui$$UI.getSetting('view_clip');
            }

            // Changing the viewport may change the state of
            // the dragging button
            app$ui$$UI.updateViewDrag();
        },

    /* ------^-------
     * /VIEW CLIPPING
     * ==============
     *    VIEWDRAG
     * ------v------*/

        toggleViewDrag() {
            if (!app$ui$$UI.rfb) return;

            app$ui$$UI.rfb.dragViewport = !app$ui$$UI.rfb.dragViewport;
            app$ui$$UI.updateViewDrag();
        },

        updateViewDrag() {
            if (!app$ui$$UI.connected) return;

            const viewDragButton = document.getElementById('noVNC_view_drag_button');

            if (!app$ui$$UI.rfb.clipViewport && app$ui$$UI.rfb.dragViewport) {
                // We are no longer clipping the viewport. Make sure
                // viewport drag isn't active when it can't be used.
                app$ui$$UI.rfb.dragViewport = false;
            }

            if (app$ui$$UI.rfb.dragViewport) {
                viewDragButton.classList.add("noVNC_selected");
            } else {
                viewDragButton.classList.remove("noVNC_selected");
            }

            // Different behaviour for touch vs non-touch
            // The button is disabled instead of hidden on touch devices
            if ($$$core$util$browser$$isTouchDevice) {
                viewDragButton.classList.remove("noVNC_hidden");

                if (app$ui$$UI.rfb.clipViewport) {
                    viewDragButton.disabled = false;
                } else {
                    viewDragButton.disabled = true;
                }
            } else {
                viewDragButton.disabled = false;

                if (app$ui$$UI.rfb.clipViewport) {
                    viewDragButton.classList.remove("noVNC_hidden");
                } else {
                    viewDragButton.classList.add("noVNC_hidden");
                }
            }
        },

    /* ------^-------
     *   /VIEWDRAG
     * ==============
     *    KEYBOARD
     * ------v------*/

        showVirtualKeyboard() {
            if (!$$$core$util$browser$$isTouchDevice) return;

            const input = document.getElementById('noVNC_keyboardinput');

            if (document.activeElement == input) return;

            input.focus();

            try {
                const l = input.value.length;
                // Move the caret to the end
                input.setSelectionRange(l, l);
            } catch (err) {
                // setSelectionRange is undefined in Google Chrome
            }
        },

        hideVirtualKeyboard() {
            if (!$$$core$util$browser$$isTouchDevice) return;

            const input = document.getElementById('noVNC_keyboardinput');

            if (document.activeElement != input) return;

            input.blur();
        },

        toggleVirtualKeyboard() {
            if (document.getElementById('noVNC_keyboard_button')
                .classList.contains("noVNC_selected")) {
                app$ui$$UI.hideVirtualKeyboard();
            } else {
                app$ui$$UI.showVirtualKeyboard();
            }
        },

        onfocusVirtualKeyboard(event) {
            document.getElementById('noVNC_keyboard_button')
                .classList.add("noVNC_selected");
            if (app$ui$$UI.rfb) {
                app$ui$$UI.rfb.focusOnClick = false;
            }
        },

        onblurVirtualKeyboard(event) {
            document.getElementById('noVNC_keyboard_button')
                .classList.remove("noVNC_selected");
            if (app$ui$$UI.rfb) {
                app$ui$$UI.rfb.focusOnClick = true;
            }
        },

        keepVirtualKeyboard(event) {
            const input = document.getElementById('noVNC_keyboardinput');

            // Only prevent focus change if the virtual keyboard is active
            if (document.activeElement != input) {
                return;
            }

            // Only allow focus to move to other elements that need
            // focus to function properly
            if (event.target.form !== undefined) {
                switch (event.target.type) {
                    case 'text':
                    case 'email':
                    case 'search':
                    case 'password':
                    case 'tel':
                    case 'url':
                    case 'textarea':
                    case 'select-one':
                    case 'select-multiple':
                        return;
                }
            }

            event.preventDefault();
        },

        keyboardinputReset() {
            const kbi = document.getElementById('noVNC_keyboardinput');
            kbi.value = new Array(app$ui$$UI.defaultKeyboardinputLen).join("_");
            app$ui$$UI.lastKeyboardinput = kbi.value;
        },

        keyEvent(keysym, code, down) {
            if (!app$ui$$UI.rfb) return;

            app$ui$$UI.rfb.sendKey(keysym, code, down);
        },

        // When normal keyboard events are left uncought, use the input events from
        // the keyboardinput element instead and generate the corresponding key events.
        // This code is required since some browsers on Android are inconsistent in
        // sending keyCodes in the normal keyboard events when using on screen keyboards.
        keyInput(event) {

            if (!app$ui$$UI.rfb) return;

            const newValue = event.target.value;

            if (!app$ui$$UI.lastKeyboardinput) {
                app$ui$$UI.keyboardinputReset();
            }
            const oldValue = app$ui$$UI.lastKeyboardinput;

            let newLen;
            try {
                // Try to check caret position since whitespace at the end
                // will not be considered by value.length in some browsers
                newLen = Math.max(event.target.selectionStart, newValue.length);
            } catch (err) {
                // selectionStart is undefined in Google Chrome
                newLen = newValue.length;
            }
            const oldLen = oldValue.length;

            let inputs = newLen - oldLen;
            let backspaces = inputs < 0 ? -inputs : 0;

            // Compare the old string with the new to account for
            // text-corrections or other input that modify existing text
            for (let i = 0; i < Math.min(oldLen, newLen); i++) {
                if (newValue.charAt(i) != oldValue.charAt(i)) {
                    inputs = newLen - i;
                    backspaces = oldLen - i;
                    break;
                }
            }

            // Send the key events
            for (let i = 0; i < backspaces; i++) {
                app$ui$$UI.rfb.sendKey($$$core$input$keysym$$default.XK_BackSpace, "Backspace");
            }
            for (let i = newLen - inputs; i < newLen; i++) {
                app$ui$$UI.rfb.sendKey($$$core$input$keysymdef$$default.lookup(newValue.charCodeAt(i)));
            }

            // Control the text content length in the keyboardinput element
            if (newLen > 2 * app$ui$$UI.defaultKeyboardinputLen) {
                app$ui$$UI.keyboardinputReset();
            } else if (newLen < 1) {
                // There always have to be some text in the keyboardinput
                // element with which backspace can interact.
                app$ui$$UI.keyboardinputReset();
                // This sometimes causes the keyboard to disappear for a second
                // but it is required for the android keyboard to recognize that
                // text has been added to the field
                event.target.blur();
                // This has to be ran outside of the input handler in order to work
                setTimeout(event.target.focus.bind(event.target), 0);
            } else {
                app$ui$$UI.lastKeyboardinput = newValue;
            }
        },

    /* ------^-------
     *   /KEYBOARD
     * ==============
     *   EXTRA KEYS
     * ------v------*/

        openExtraKeys() {
            app$ui$$UI.closeAllPanels();
            app$ui$$UI.openControlbar();

            document.getElementById('noVNC_modifiers')
                .classList.add("noVNC_open");
            document.getElementById('noVNC_toggle_extra_keys_button')
                .classList.add("noVNC_selected");
        },

        closeExtraKeys() {
            document.getElementById('noVNC_modifiers')
                .classList.remove("noVNC_open");
            document.getElementById('noVNC_toggle_extra_keys_button')
                .classList.remove("noVNC_selected");
        },

        toggleExtraKeys() {
            if (document.getElementById('noVNC_modifiers')
                .classList.contains("noVNC_open")) {
                app$ui$$UI.closeExtraKeys();
            } else  {
                app$ui$$UI.openExtraKeys();
            }
        },

        sendEsc() {
            app$ui$$UI.rfb.sendKey($$$core$input$keysym$$default.XK_Escape, "Escape");
        },

        sendTab() {
            app$ui$$UI.rfb.sendKey($$$core$input$keysym$$default.XK_Tab);
        },

        toggleCtrl() {
            const btn = document.getElementById('noVNC_toggle_ctrl_button');
            if (btn.classList.contains("noVNC_selected")) {
                app$ui$$UI.rfb.sendKey($$$core$input$keysym$$default.XK_Control_L, "ControlLeft", false);
                btn.classList.remove("noVNC_selected");
            } else {
                app$ui$$UI.rfb.sendKey($$$core$input$keysym$$default.XK_Control_L, "ControlLeft", true);
                btn.classList.add("noVNC_selected");
            }
        },

        toggleWindows() {
            const btn = document.getElementById('noVNC_toggle_windows_button');
            if (btn.classList.contains("noVNC_selected")) {
                app$ui$$UI.rfb.sendKey($$$core$input$keysym$$default.XK_Super_L, "MetaLeft", false);
                btn.classList.remove("noVNC_selected");
            } else {
                app$ui$$UI.rfb.sendKey($$$core$input$keysym$$default.XK_Super_L, "MetaLeft", true);
                btn.classList.add("noVNC_selected");
            }
        },

        toggleAlt() {
            const btn = document.getElementById('noVNC_toggle_alt_button');
            if (btn.classList.contains("noVNC_selected")) {
                app$ui$$UI.rfb.sendKey($$$core$input$keysym$$default.XK_Alt_L, "AltLeft", false);
                btn.classList.remove("noVNC_selected");
            } else {
                app$ui$$UI.rfb.sendKey($$$core$input$keysym$$default.XK_Alt_L, "AltLeft", true);
                btn.classList.add("noVNC_selected");
            }
        },

        sendCtrlAltDel() {
            app$ui$$UI.rfb.sendCtrlAltDel();
        },

    /* ------^-------
     *   /EXTRA KEYS
     * ==============
     *     PVE
     * ------v------*/

        togglePVECommandPanel: function() {
            if (document.getElementById('pve_commands').classList.contains("noVNC_open")) {
                app$ui$$UI.closePVECommandPanel();
            } else {
                app$ui$$UI.openPVECommandPanel();
            }
        },

        openPVECommandPanel: function() {
            var me = this;
            app$ui$$UI.closeAllPanels();
            app$ui$$UI.openControlbar();

            document.getElementById('pve_commands').classList.add("noVNC_open");
            document.getElementById('pve_commands_button').classList.add("noVNC_selected");
        },

        closePVECommandPanel: function() {
            document.getElementById('pve_commands').classList.remove("noVNC_open");
            document.getElementById('pve_commands_button').classList.remove("noVNC_selected");
        },

        updateSessionSize: function(e) {
            var rfb = e.detail.rfb;
            var width = e.detail.width;
            var height = e.detail.height;
            app$ui$$UI.PVE.updateFBSize(rfb, width, height);

            app$ui$$UI.applyResizeMode();
            app$ui$$UI.updateViewClip();
        },

    /* ------^-------
     *    /PVE
     * ==============
     *     MISC
     * ------v------*/
        setMouseButton(num) {
            const view_only = app$ui$$UI.rfb.viewOnly;
            if (app$ui$$UI.rfb && !view_only) {
                app$ui$$UI.rfb.touchButton = num;
            }

            const blist = [0, 1, 2, 4];
            for (let b = 0; b < blist.length; b++) {
                const button = document.getElementById('noVNC_mouse_button' +
                                                     blist[b]);
                if (blist[b] === num && !view_only) {
                    button.classList.remove("noVNC_hidden");
                } else {
                    button.classList.add("noVNC_hidden");
                }
            }
        },

        updateLocalCursor() {
            if (!app$ui$$UI.rfb) return;
            app$ui$$UI.rfb.localCursor = app$ui$$UI.getSetting('local_cursor');
        },

        updateViewOnly() {
            if (!app$ui$$UI.rfb) return;
            app$ui$$UI.rfb.viewOnly = app$ui$$UI.getSetting('view_only');

            // Hide input related buttons in view only mode
            if (app$ui$$UI.rfb.viewOnly) {
                document.getElementById('noVNC_keyboard_button')
                    .classList.add('noVNC_hidden');
                document.getElementById('noVNC_toggle_extra_keys_button')
                    .classList.add('noVNC_hidden');
                document.getElementById('noVNC_mouse_button' + app$ui$$UI.rfb.touchButton)
                    .classList.add('noVNC_hidden');
            } else {
                document.getElementById('noVNC_keyboard_button')
                    .classList.remove('noVNC_hidden');
                document.getElementById('noVNC_toggle_extra_keys_button')
                    .classList.remove('noVNC_hidden');
                document.getElementById('noVNC_mouse_button' + app$ui$$UI.rfb.touchButton)
                    .classList.remove('noVNC_hidden');
            }
        },

        updateShowDotCursor() {
            if (!app$ui$$UI.rfb) return;
            app$ui$$UI.rfb.showDotCursor = app$ui$$UI.getSetting('show_dot');
        },

        updateLogging() {
            $$webutil$$.init_logging(app$ui$$UI.getSetting('logging'));
        },

        updateDesktopName(e) {
            app$ui$$UI.desktopName = e.detail.name;
            // Display the desktop name in the document title
            document.title = e.detail.name + " - noVNC";
        },

        bell(e) {
            if ($$webutil$$.getConfigVar('bell', 'on') === 'on') {
                const promise = document.getElementById('noVNC_bell').play();
                // The standards disagree on the return value here
                if (promise) {
                    promise.catch((e) => {
                        if (e.name === "NotAllowedError") {
                            // Ignore when the browser doesn't let us play audio.
                            // It is common that the browsers require audio to be
                            // initiated from a user action.
                        } else {
                            $$$core$util$logging$$.Error("Unable to play bell: " + e);
                        }
                    });
                }
            }
        },

        //Helper to add options to dropdown.
        addOption(selectbox, text, value) {
            const optn = document.createElement("OPTION");
            optn.text = text;
            optn.value = value;
            selectbox.options.add(optn);
        },

    /* ------^-------
     *    /MISC
     * ==============
     */
    };

    // Set up translations
    const app$ui$$LINGUAS = ["cs", "de", "el", "es", "ko", "nl", "pl", "ru", "sv", "tr", "zh_CN", "zh_TW"];
    $$localization$$l10n.setup(app$ui$$LINGUAS);
    if ($$localization$$l10n.language === "en" || $$localization$$l10n.dictionary !== undefined) {
        app$ui$$UI.prime();
    } else {
        $$webutil$$.fetchJSON('/staticfiles/novnc/app/locale/' + $$localization$$l10n.language + '.json')
            .then((translations) => { $$localization$$l10n.dictionary = translations; })
            .catch(err => $$$core$util$logging$$.Error("Failed to load translations: " + err))
            .then(app$ui$$UI.prime);
    }

    var app$ui$$default = app$ui$$UI;
}).call(this);