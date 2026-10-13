-- | Local UI-flow layout on top of Rex's public document API. The upstream
-- printer still owns calls, records, strings, and width-sensitive wrapping.
-- Only flow bodies get a mandatory newline and two-space indentation.
module Goo.Rex.Layout (printRex) where

import Rex.PDoc (PDoc (..), pdocText, pdocParens, pdocIntersperse, render)
import Rex.PrintRex (defaultConfig, rexDoc)
import Rex.Rex (Rex (..), Color (..))

printRex :: Int -> Rex -> String
printRex width = render width . document

-- Group a top-level flow so its line breaks remain one Rex expression.
-- Recognizing the same grouped shape on input makes formatting idempotent.
document :: Rex -> PDoc
document (EXPR _ color [heading, EXPR _ CURLY children])
    | color `elem` [CLEAR, PAREN] = pdocParens (flow heading children)
document (EXPR _ CURLY children) = block PEmpty children
document tree = rexDoc defaultConfig tree

flow :: Rex -> [Rex] -> PDoc
flow heading = block (PCat (rexDoc defaultConfig heading) PSpace)

-- Capture indentation at the start of the flow, not at the opening brace
-- after its potentially long configuration. Child flows then nest by two.
block :: PDoc -> [Rex] -> PDoc
block heading [] = PCat heading (pdocText "{}")
block heading children = PDent $ concatenate
    [ heading, PChar '{', PLine, pdocText "  "
    , PDent (pdocIntersperse PLine (childDocuments children))
    , PLine, PChar '}'
    ]

-- In Rex an unparenthesized flow's head and body are adjacent siblings.
-- Keep them together; every atom or nested flow starts on its own line.
childDocuments :: [Rex] -> [PDoc]
childDocuments [] = []
childDocuments (heading : EXPR _ CURLY children : rest) =
    flow heading children : childDocuments rest
childDocuments (tree : rest) = document tree : childDocuments rest

concatenate :: [PDoc] -> PDoc
concatenate = foldr PCat PEmpty
