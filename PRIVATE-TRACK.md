# The private track

A check runs on one of two tracks. Which one is the choice of the person who asks.

| | Open track | Private track |
|---|---|---|
| Material | public files at a commit, or an Internet-Draft revision, linked in the public form | sent by email, never posted in the public issue |
| Mapping, expected results, runs | public in [WEXP-dev/wexp-interop](https://github.com/WEXP-dev/wexp-interop), frozen before any run | the same procedure, done by hand in a directory outside any public repository |
| Appraisers | the two public appraisers | the same two public appraisers, run locally on your material |
| What is published | everything, with the wording of the result agreed with you | only what you agree to (see below) |

## How the private track works

1. **Ask in the public form and tick the private-material box.** Put nothing private in the
   form. The public issue holds only what you are content to have public, which can be as little
   as a project name.
2. **A maintainer replies in the issue** to confirm that the case can go on the private track.
   Until then, send nothing.
3. **Send the material by email** to the address the maintainer gives. Each file is pinned by its
   SHA-256 on receipt, so everything after refers to those exact bytes.
4. **The mapping and the expected results are written down and agreed with you before either
   appraiser runs**, exactly as on the open track. You review them by email.
5. **Both appraisers run locally** on the frozen inputs. No input, mapping or result is uploaded
   to any public place, and none of it is used for anything else.
6. **You decide what becomes public**, and you can decide later:
   - nothing at all;
   - a one-line note that a check took place, with what was examined described in words you agree;
   - that note with the SHA-256 of the material, so that the material can later be shown to be the
     one examined without revealing it.

   Whatever you choose, the note says who initiated the check and how that was established, in
   the same terms as on the open track, or that the initiator asked not to be named.

## What the private track does not offer

- No response-time commitment. It is handled by hand and is experimental.
- No confidentiality agreement and no secure transfer beyond ordinary email. Do not send
  credentials, keys, personal data of other people, or anything you are not free to share with one
  outside reader.
- No statement that your material conforms to WEXP, on either track.

## Moving between tracks

Untick the box and add public links to move a check to the open track; the automatic reply and the
route label follow the edit. A check can move from open to private only for material that has not
yet been posted: what is already public in the issue stays public.
