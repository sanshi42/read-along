import assert from "node:assert/strict";
import test from "node:test";

import {
  isRectFullyVisibleWithinReaderChrome,
  normalizeReadingTitle,
  scrollTargetForRectWithinReaderChrome,
  shouldShowReaderNavContext,
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

test("scrollTargetForRectWithinReaderChrome centers short sentences in the readable band", () => {
  const target = scrollTargetForRectWithinReaderChrome(
    { top: 1094, bottom: 1173, height: 79 },
    2001.5,
    { top: 78, bottom: 704 },
  );

  assert.equal(Math.round(target), 2744);
});
