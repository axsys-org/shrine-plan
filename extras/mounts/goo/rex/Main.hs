{-# LANGUAGE OverloadedStrings, LambdaCase, ScopedTypeVariables #-}
-- Retained syntax component: only upstream Rex and the small display layout adapter.
-- No Goo semantic, diagnostic, lowering, or rendering modules are linked.
import Control.Exception (SomeException, SomeAsyncException, fromException, evaluate, tryJust)
import Data.Aeson
import Data.Aeson.Types (Parser, parseEither)
import qualified Data.ByteString.Lazy.Char8 as BL
import qualified Data.Vector as V
import Data.Maybe (mapMaybe)
import qualified Data.Text as T
import Rex.Rex
import Rex.Lex (Span(..))
import Rex.Error (BadReason(..))
import Rex.Tree2 (parseRex)
import qualified Rex.PrintRex as P
import qualified Goo.Rex.Layout as Layout

spanJSON (Span l c o n) = toJSON [l,c,o,n]
shapeJSON = \case
  WORD -> String "word"; QUIP -> String "quip"; CORD -> String "cord"
  TAPE -> String "tape"; PAGE -> String "page"; SPAN -> String "span"; SLUG -> String "slug"
  BAD r -> object ["bad" .= reason r]
reason :: BadReason -> String
reason = \case
  InvalidChar -> "invalid-char"; UnclosedTrad -> "unclosed-trad"; UnclosedUgly -> "unclosed-ugly"
  MismatchedBracket -> "mismatched-bracket"; InvalidPage -> "invalid-page"; InvalidSpan -> "invalid-span"
color c = T.toLower (T.pack (show c))
node n = object (base ++ fields) where
  (tag,sp,fields) = case n of
    LEAF s sh t -> ("leaf",s,["shape" .= shapeJSON sh,"text" .= t])
    NEST s c r xs -> ("nest",s,["color" .= color c,"rune" .= r,"kids" .= map node xs])
    EXPR s c xs -> ("expr",s,["color" .= color c,"kids" .= map node xs])
    PREF s r x -> ("pref",s,["rune" .= r,"kid" .= node x])
    TYTE s r xs -> ("tyte",s,["rune" .= r,"kids" .= map node xs])
    BLOC s c r h xs -> ("bloc",s,["color" .= color c,"rune" .= r,"head" .= node h,"kids" .= map node xs])
    OPEN s r xs -> ("open",s,["rune" .= r,"kids" .= map node xs])
    JUXT s xs -> ("juxt",s,["kids" .= map node xs])
    HEIR s xs -> ("heir",s,["kids" .= map node xs])
  base = ["tag" .= (tag::String),"span" .= spanJSON sp]
readSpan v = do
  xs <- parseJSON v
  case xs of
    [l,c,o,n] | all (>=0) xs -> pure (Span l c o n)
    _ -> fail "span must contain four nonnegative integers"
readColor v = parseJSON v >>= \case
  "paren" -> pure PAREN; "brack" -> pure BRACK; "curly" -> pure CURLY; "clear" -> pure CLEAR
  (_::String) -> fail "unknown color"
readReason v = parseJSON v >>= \case
  "invalid-char" -> pure InvalidChar; "unclosed-trad" -> pure UnclosedTrad
  "unclosed-ugly" -> pure UnclosedUgly; "mismatched-bracket" -> pure MismatchedBracket
  "invalid-page" -> pure InvalidPage; "invalid-span" -> pure InvalidSpan
  (_::String) -> fail "unknown bad reason"
readShape (String s) = case s of
  "word" -> pure WORD; "quip" -> pure QUIP; "cord" -> pure CORD; "tape" -> pure TAPE
  "page" -> pure PAGE; "span" -> pure SPAN; "slug" -> pure SLUG; _ -> fail "unknown leaf shape"
readShape v = withObject "bad shape" (\o -> BAD <$> (o .: "bad" >>= readReason)) v
readNode = withObject "Rex node" $ \o -> do
  tag <- o .: "tag" :: Parser String
  s <- o .: "span" >>= readSpan
  let kids = o .: "kids" >>= traverse readNode
      col = o .: "color" >>= readColor
  case tag of
    "leaf" -> LEAF s <$> (o .: "shape" >>= readShape) <*> o .: "text"
    "nest" -> NEST s <$> col <*> o .: "rune" <*> kids
    "expr" -> EXPR s <$> col <*> kids
    "pref" -> PREF s <$> o .: "rune" <*> (o .: "kid" >>= readNode)
    "tyte" -> TYTE s <$> o .: "rune" <*> kids
    "bloc" -> BLOC s <$> col <*> o .: "rune" <*> (o .: "head" >>= readNode) <*> kids
    "open" -> OPEN s <$> o .: "rune" <*> kids
    "juxt" -> JUXT s <$> kids
    "heir" -> HEIR s <$> kids
    _ -> fail "unknown node tag"
-- Compact printer-only transport. Full spans and every Rex form are preserved.
readCompact = withArray "compact Rex" $ \v -> case V.toList v of
  [String "leaf",s,sh,t] -> LEAF <$> readSpan s <*> readShape sh <*> parseJSON t
  [String "nest",s,c,r,xs] -> NEST <$> readSpan s <*> readColor c <*> parseJSON r <*> children xs
  [String "expr",s,c,xs] -> EXPR <$> readSpan s <*> readColor c <*> children xs
  [String "pref",s,r,x] -> PREF <$> readSpan s <*> parseJSON r <*> readCompact x
  [String "tyte",s,r,xs] -> TYTE <$> readSpan s <*> parseJSON r <*> children xs
  [String "bloc",s,c,r,h,xs] -> BLOC <$> readSpan s <*> readColor c <*> parseJSON r <*> readCompact h <*> children xs
  [String "open",s,r,xs] -> OPEN <$> readSpan s <*> parseJSON r <*> children xs
  [String "juxt",s,xs] -> JUXT <$> readSpan s <*> children xs
  [String "heir",s,xs] -> HEIR <$> readSpan s <*> children xs
  _ -> fail "invalid compact Rex node"
 where children = withArray "Rex children" (traverse readCompact . V.toList)
response fields = object (["version" .= (1::Int), "ok" .= True] ++ fields)
command = withObject "request" $ \o -> do
  version <- o .: "version" :: Parser Int
  if version /= 1 then fail "unsupported version" else pure ()
  action <- o .: "action" :: Parser String
  case action of
    "parse" -> do
      src <- o .: "source"
      let trees = mapMaybe (uncurry rexFromBlockTree) (parseRex src)
      pure (response ["trees" .= map node trees])
    "echo" -> do
      trees <- o .: "trees" >>= traverse readNode
      pure (response ["trees" .= map node trees])
    "print" -> do
      trees <- o .: "trees" >>= traverse readNode
      pure (response ["texts" .= map (P.printRex 50) trees])
    "goo-print-compact" -> do
      batches <- o .: "batches" >>= traverse (withArray "Rex batch" (traverse readCompact . V.toList))
      pure (response ["texts" .= map (T.intercalate "\n\n" . map (T.pack . Layout.printRex 50 . grouped)) batches])
    "goo-print" -> do
      trees <- o .: "trees" >>= traverse readNode
      pure (response ["text" .= T.intercalate "\n\n" (map (T.pack . Layout.printRex 50 . grouped) trees)])
    _ -> fail "unknown action"
grouped (EXPR sp CLEAR xs) = EXPR sp PAREN xs
grouped tree = tree
failure msg = object ["version" .= (1::Int),"ok" .= False,"error" .= (msg::String)]
run value = do
  result <- tryJust synchronous (evaluate (BL.toStrict (encode (either failure id (parseEither command value)))))
  pure $ case result of
    Left e -> failure (show (e::SomeException))
    Right bytes -> either failure id (eitherDecodeStrict bytes)
  where
    synchronous :: SomeException -> Maybe SomeException
    synchronous e = case fromException e :: Maybe SomeAsyncException of
      Just _ -> Nothing
      Nothing -> Just e
main = do
  value <- eitherDecode <$> BL.getContents
  result <- case value of
    Left err -> pure (failure err)
    Right (Array xs) -> toJSON <$> traverse run (V.toList xs)
    Right request -> run request
  BL.putStrLn (encode result)
