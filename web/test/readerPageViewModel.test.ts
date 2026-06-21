import assert from "node:assert/strict";
import test from "node:test";

import {
  isRectFullyVisibleWithinReaderChrome,
  normalizeReadingTitle,
  readerChromeBoundsForFixedControls,
  readerContextProgressLabel,
  readerSentenceInteraction,
  sentencePointerAction,
  scrollTargetForRectWithinReaderChrome,
  shouldShowReaderNavContext,
  zenModeShortcutAction,
} from "../src/routes/readerPageViewModel.ts";

test("normalizeReadingTitle removes only a final PDF extension", () => {
  assert.equal(
    normalizeReadingTitle("6 底注 16 回合爆机攻略 - 文字版.pdf"),
    "6 底注 16 回合爆机攻略 - 文字版",
  );
  assert.equal(normalizeReadingTitle("PDF 阅读技巧"), "PDF 阅读技巧");
});

test("shouldShowReaderNavContext appears after the material header leaves the navigation area", () => {
  assert.equal(shouldShowReaderNavContext({ headerBottom: 92, navBottom: 68 }), false);
  assert.equal(shouldShowReaderNavContext({ headerBottom: 68, navBottom: 68 }), true);
});

test("readerContextProgressLabel leads with sentence position when available", () => {
  assert.equal(
    readerContextProgressLabel({
      sentenceIndex: 4,
      sentenceCount: 12,
      timelinePositionLabel: "01:20 / 08:00",
      timelineTotalLabel: "08:00",
    }),
    "第 5 / 12 句 · 01:20 / 08:00",
  );
  assert.equal(
    readerContextProgressLabel({
      sentenceIndex: -1,
      sentenceCount: 12,
      timelinePositionLabel: "",
      timelineTotalLabel: "08:00",
    }),
    "共 12 句 · 08:00",
  );
});

test("isRectFullyVisibleWithinReaderChrome treats fixed player overlap as not visible", () => {
  const bounds = { top: 78, bottom: 704 };

  assert.equal(
    isRectFullyVisibleWithinReaderChrome({ top: 110, bottom: 180, height: 70 }, bounds),
    true,
  );
  assert.equal(
    isRectFullyVisibleWithinReaderChrome({ top: 660, bottom: 730, height: 70 }, bounds),
    false,
  );
});

test("readerChromeBoundsForFixedControls keeps fixed player overlap out of the readable band", () => {
  assert.deepEqual(
    readerChromeBoundsForFixedControls({
      viewportHeight: 844,
      navBottom: 60,
      playerTop: 704,
      margin: 18,
    }),
    { top: 78, bottom: 686 },
  );
  assert.deepEqual(
    readerChromeBoundsForFixedControls({
      viewportHeight: 320,
      navBottom: 84,
      playerTop: 118,
      margin: 18,
    }),
    { top: 102, bottom: 100 },
  );
});

test("scrollTargetForRectWithinReaderChrome centers short sentences in the readable band", () => {
  const target = scrollTargetForRectWithinReaderChrome(
    { top: 1094, bottom: 1173, height: 79 },
    2001.5,
    { top: 78, bottom: 704 },
  );

  assert.equal(Math.round(target), 2744);
});

test("sentencePointerAction keeps single click for selecting and double click for playback", () => {
  assert.equal(sentencePointerAction(1), "select");
  assert.equal(sentencePointerAction(2), "play");
});

test("readerSentenceInteraction keeps prose quiet except for the current sentence", () => {
  assert.deepEqual(
    readerSentenceInteraction({
      sentenceIndex: 4,
      sentenceCount: 12,
      isCurrent: false,
      isPlaying: false,
    }),
    {},
  );
  assert.deepEqual(
    readerSentenceInteraction({
      sentenceIndex: 4,
      sentenceCount: 12,
      isCurrent: true,
      isPlaying: true,
    }),
    {
      ariaCurrent: "location",
      ariaLabel: "正在播放，第 5 / 12 句。按 Enter 播放或暂停；双击任意句可从该句播放。",
      tabIndex: 0,
    },
  );
});

test("zenModeShortcutAction toggles with Z only outside interactive targets", () => {
  assert.equal(
    zenModeShortcutAction({ key: "z" }, { zenMode: false, interactiveTarget: false }),
    "toggle",
  );
  assert.equal(
    zenModeShortcutAction({ key: "Z", shiftKey: true }, { zenMode: true, interactiveTarget: false }),
    "toggle",
  );
  assert.equal(
    zenModeShortcutAction({ key: "z" }, { zenMode: false, interactiveTarget: true }),
    null,
  );
});

test("zenModeShortcutAction exits with Escape only while zen mode is active", () => {
  assert.equal(
    zenModeShortcutAction({ key: "Escape" }, { zenMode: true, interactiveTarget: true }),
    "exit",
  );
  assert.equal(
    zenModeShortcutAction({ key: "Escape" }, { zenMode: false, interactiveTarget: false }),
    null,
  );
});

test("zenModeShortcutAction ignores modified shortcuts", () => {
  assert.equal(
    zenModeShortcutAction({ key: "z", metaKey: true }, { zenMode: false, interactiveTarget: false }),
    null,
  );
  assert.equal(
    zenModeShortcutAction({ key: "z", ctrlKey: true }, { zenMode: false, interactiveTarget: false }),
    null,
  );
  assert.equal(
    zenModeShortcutAction({ key: "z", altKey: true }, { zenMode: false, interactiveTarget: false }),
    null,
  );
});
