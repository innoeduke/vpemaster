-- Wrap emoji / missing-glyph codepoints in a raw LaTeX command that switches
-- to the \emojifont (defined in .latex-emoji-header.tex).

-- Wrap any supplementary-plane codepoint (U+10000 and above) in {\emojifont ...}
-- so they render via Noto Emoji. Body fonts (Latin Modern, DejaVu) don't carry
-- supplementary-plane glyphs, but BMP symbols (U+2600..U+27FF) usually do.
local function is_emoji(cp)
  return cp >= 0x10000
end

function Str(elem)
  local text = elem.text
  if not text or text == "" then return nil end

  local out = {}
  local buf = ""
  for _, cp in utf8.codes(text) do
    if is_emoji(cp) then
      if buf ~= "" then
        table.insert(out, pandoc.Str(buf))
        buf = ""
      end
      table.insert(out, pandoc.RawInline("latex", "{\\emojifont{}" .. utf8.char(cp) .. "}"))
    else
      buf = buf .. utf8.char(cp)
    end
  end
  if buf ~= "" then table.insert(out, pandoc.Str(buf)) end
  if #out > 0 then return out end
end
