const WORD = 'Aletheia'
const MS_BETWEEN_LETTERS = 110

// The large wordmark. Every letter runs the same slow fade (see
// --animate-fade-in in index.css); each one starts a little later than the
// letter before it. The word then stays.
export function AnimatedWordmark() {
  return (
    // text-box trims the empty space a font keeps above capitals and below the
    // baseline, so the box is exactly as tall as the letters and centres truly.
    // 'opsz' 72 selects Newsreader's display cut: thin hairlines and sharp serifs,
    // drawn for large sizes.
    <p className="font-display text-8xl leading-none font-medium tracking-tight [font-variation-settings:'opsz'_72] [text-box:trim-both_cap_alphabetic] xl:text-9xl">
      {/* Screen readers get the whole word once, not letter by letter. */}
      <span className="sr-only">{WORD}</span>
      {/* motion-reduce: people who ask their system for reduced motion see the
          full word at once. */}
      {[...WORD].map((letter, index) => (
        <span
          key={index}
          aria-hidden="true"
          className="animate-fade-in motion-reduce:animate-none"
          style={{ animationDelay: `${index * MS_BETWEEN_LETTERS}ms` }}
        >
          {letter}
        </span>
      ))}
    </p>
  )
}
