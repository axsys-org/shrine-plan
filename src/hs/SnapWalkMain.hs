-- Copyright (c) 2026 xoCore Technologies, Benjamin Summers
-- SPDX-License-Identifier: MIT
-- See LICENSE for full terms.

{-# LANGUAGE LambdaCase, BlockArguments, OverloadedStrings #-}

module Main where

import Control.Exception (SomeException, displayException, try)
import Control.Monad (foldM)
import qualified Data.ByteString.Base58 as Base58
import qualified Data.ByteString.Char8 as BS8
import Data.Char (isSpace)
import Data.List (intercalate, isPrefixOf, sortOn)
import Data.Maybe (fromMaybe, mapMaybe)
import Data.Ord (Down(..))
import qualified Data.Set as Set
import Data.Set (Set)
import qualified Data.Vector as V
import Numeric.Natural (Natural)
import System.Directory (getFileSize)
import System.Environment (getArgs)
import System.Exit (exitFailure, exitSuccess)
import System.FilePath ((</>))
import System.IO
import Text.Read (readMaybe)

import Plan (InActor, withNewRts)
import PlanAssembler (loadAssemblyQuiet)
import Print (natShowStr, prettyValMulti)
import Types

data Cursor = Cursor
    { curRoot   :: Val
    , curFocus  :: Val
    , curCrumbs :: [Crumb]
    }

data Crumb = Crumb
    { crumbKey    :: String
    , crumbParent :: Val
    }

data Child = Child
    { childKey     :: String
    , childAliases :: [String]
    , childTitle   :: String
    , childValue   :: Val
    }

data SortOrder = Asc | Desc

data PinInfo = PinInfo
    { pinInfoHash :: String
    , pinInfoSize :: Maybe Integer
    , pinInfoVal  :: Val
    }

data PinLookup
    = PinFound String Val
    | PinMissing String
    | PinAmbiguous String [String]

main :: IO ()
main = withNewRts do
    hSetBuffering stdout NoBuffering
    hSetBuffering stdin LineBuffering
    getArgs >>= \case
        [] -> loadLatest >>= start
        [hash] -> loadHash hash >>= start
        _ -> usage >> exitFailure

usage :: IO ()
usage = do
    putStrLn "Usage: snap-walk [snapshot-hash]"
    putStrLn "Without a hash, loads the last entry from snap/root.plan."

loadLatest :: InActor => IO (String, Val)
loadLatest = do
    hash <- latestSnapshotHash "snap"
    val  <- loadSnapshotHash hash
    pure (hash, val)

loadHash :: InActor => String -> IO (String, Val)
loadHash hash = do
    val <- loadSnapshotHash hash
    pure (hash, val)

loadSnapshotHash :: InActor => String -> IO Val
loadSnapshotHash hash = do
    result <- try (loadAssemblyQuiet "snap" hash (Just "_")) :: IO (Either SomeException Val)
    case result of
        Left e -> do
            hPutStrLn stderr $ "Could not load snapshot " <> hash <> ": "
                            <> displayException e
            exitFailure
        Right val -> pure val

latestSnapshotHash :: FilePath -> IO String
latestSnapshotHash snapDir = do
    result <- try (readFile (snapDir </> "root.plan")) :: IO (Either SomeException String)
    case result of
        Left e -> do
            hPutStrLn stderr $ "Could not read " <> (snapDir </> "root.plan") <> ": "
                            <> displayException e
            exitFailure
        Right txt ->
            case reverse (mapMaybe rootLineHash (lines txt)) of
                hash : _ -> pure hash
                [] -> do
                    hPutStrLn stderr $ "No snapshot hashes found in " <> (snapDir </> "root.plan")
                    exitFailure

rootLineHash :: String -> Maybe String
rootLineHash line =
    case dropWhile isSpace line of
        '@' : rest ->
            case takeWhile (not . isSpace) rest of
                [] -> Nothing
                xs -> Just xs
        _ -> Nothing

start :: InActor => (String, Val) -> IO ()
start (hash, rootVal) = do
    putStrLn $ "Loaded snap/" <> hash <> ".plan"
    putStrLn "Type :help for commands."
    putStrLn ""
    let cur = Cursor rootVal rootVal []
    printHere cur
    loop cur

loop :: InActor => Cursor -> IO ()
loop cur = do
    putStr $ prompt cur
    hFlush stdout
    isEOF >>= \case
        True -> putStrLn "" >> exitSuccess
        False -> do
            line <- trim <$> getLine
            dispatch cur line >>= loop

dispatch :: InActor => Cursor -> String -> IO Cursor
dispatch cur "" = printHere cur >> pure cur
dispatch cur line =
    case words line of
        [":help"]      -> putStr helpText >> pure cur
        [":h"]         -> putStr helpText >> pure cur
        ["help"]       -> putStr helpText >> pure cur
        ["?"]          -> putStr helpText >> pure cur
        [":quit"]      -> exitSuccess
        [":q"]         -> exitSuccess
        ["quit"]       -> exitSuccess
        ["q"]          -> exitSuccess
        ["pwd"]        -> putStrLn (formatPath cur) >> pure cur
        ["type"]       -> putStrLn (summary (curFocus cur)) >> pure cur
        ["ls"]         -> listChildren cur >> pure cur
        ["children"]   -> listChildren cur >> pure cur
        ["pins"]       -> listPins Desc (curRoot cur) >> pure cur
        ["pins", ord]  -> case parseSortOrder ord of
            Just sortOrder -> listPins sortOrder (curRoot cur) >> pure cur
            Nothing -> putStrLn "Usage: pins [asc|desc]" >> pure cur
        ["pin"]        -> putStrLn "Usage: pin <hash-or-prefix>" >> pure cur
        ["pin", hash]  -> movePin cur hash
        ["show"]       -> showFocus 100 cur >> pure cur
        ["show", w]    -> showFocus (readWidth w) cur >> pure cur
        ["cat"]        -> showFocus 100 cur >> pure cur
        ["cat", w]     -> showFocus (readWidth w) cur >> pure cur
        ["hash"]       -> printHash cur >> pure cur
        ["root"]       -> moveRoot cur
        ["cd", path]   -> movePath cur path
        ["go", path]   -> movePath cur path
        ["open", path] -> movePath cur path
        ["up"]         -> movePath cur ".."
        [".."]         -> movePath cur ".."
        ['@' : hash]   -> movePin cur hash
        [path]         -> movePath cur path
        _ -> do
            putStrLn "Unknown command. Type :help for commands."
            pure cur

readWidth :: String -> Int
readWidth s = fromMaybe 100 (readMaybe s)

helpText :: String
helpText = unlines
    [ ""
    , "Commands"
    , "  ls                  List children of the current value"
    , "  cd <child/path>     Move to a child; supports /, ., and .."
    , "  <child/path>        Shortcut for cd <child/path>"
    , "  up, ..              Move to the parent"
    , "  root                Move back to the snapshot root"
    , "  pwd                 Show the current path"
    , "  type                Show the current value summary"
    , "  show [width]        Pretty-print the current value"
    , "  hash                Show the current pin hash, if this is a pin"
    , "  pins [asc|desc]     List recursive snapshot pins by file size"
    , "  pin <hash>          Jump to a recursive pin by hash or prefix"
    , "  @<hash>             Shortcut for pin <hash>"
    , "  help, ?, :help      Show this message"
    , "  quit, q, :quit      Exit"
    , ""
    , "Child names"
    , "  Pin: inner, sub0, sub1, ..."
    , "  Law: tag, body"
    , "  App: head, 0, 1, ..."
    , ""
    ]

prompt :: Cursor -> String
prompt cur = "snap:" <> formatPath cur <> "> "

formatPath :: Cursor -> String
formatPath cur =
    case reverse (map crumbKey (curCrumbs cur)) of
        [] -> "/"
        xs -> "/" <> intercalate "/" xs

printHere :: Cursor -> IO ()
printHere cur = do
    putStrLn $ formatPath cur <> "  " <> summary (curFocus cur)
    let n = length (children (curFocus cur))
    putStrLn $ show n <> " child" <> if n == 1 then "" else "ren"

listChildren :: Cursor -> IO ()
listChildren cur =
    case children (curFocus cur) of
        [] -> putStrLn "(no children)"
        xs -> mapM_ printChild xs
  where
    printChild child =
        putStrLn $ padRight 8 (childKey child)
                <> padRight 14 (childTitle child)
                <> preview (childValue child)

listPins :: SortOrder -> Val -> IO ()
listPins order rootVal = do
    infos <- mapM pinInfo (recursivePins rootVal)
    let sorted = sortPins order infos
    putStrLn $ show (length sorted) <> " pin(s), sorted by file size "
            <> orderLabel order <> ":"
    putStrLn $ padLeft 10 "bytes" <> "  hash"
    mapM_ printPin sorted
  where
    printPin info =
        putStrLn $ padLeft 10 (sizeText (pinInfoSize info))
                <> "  " <> pinInfoHash info
                <> "  " <> preview (pinInfoVal info)

pinInfo :: Val -> IO PinInfo
pinInfo val@(P hash _ _) = do
    let hashText = hashB58 hash
    size <- fileSizeMaybe ("snap" </> (hashText <> ".plan"))
    pure PinInfo
        { pinInfoHash = hashText
        , pinInfoSize = size
        , pinInfoVal  = val
        }
pinInfo val = pure PinInfo
    { pinInfoHash = "(not-a-pin)"
    , pinInfoSize = Nothing
    , pinInfoVal  = val
    }

fileSizeMaybe :: FilePath -> IO (Maybe Integer)
fileSizeMaybe path = do
    result <- try (getFileSize path) :: IO (Either SomeException Integer)
    pure $ either (const Nothing) Just result

recursivePins :: Val -> [Val]
recursivePins rootVal = go Set.empty [rootVal]
  where
    go :: Set BS8.ByteString -> [Val] -> [Val]
    go _ [] = []
    go seen (v : rest) =
        case v of
            P hash subPins inner
                | Set.member hash seen -> go seen rest
                | otherwise ->
                    v : go (Set.insert hash seen) (subPins <> (inner : rest))
            L _ tag body ->
                go seen (tag : body : rest)
            A f xs ->
                go seen (f : V.toList xs <> rest)
            N{} ->
                go seen rest

sortPins :: SortOrder -> [PinInfo] -> [PinInfo]
sortPins Asc  = sortOn pinSizeKey
sortPins Desc = sortOn (Down . pinSizeKey)

pinSizeKey :: PinInfo -> Integer
pinSizeKey = fromMaybe (-1) . pinInfoSize

parseSortOrder :: String -> Maybe SortOrder
parseSortOrder "asc"  = Just Asc
parseSortOrder "desc" = Just Desc
parseSortOrder _      = Nothing

orderLabel :: SortOrder -> String
orderLabel Asc  = "ascending"
orderLabel Desc = "descending"

sizeText :: Maybe Integer -> String
sizeText Nothing  = "missing"
sizeText (Just n) = show n

showFocus :: Int -> Cursor -> IO ()
showFocus width cur = putStrLn (prettyValMulti width (curFocus cur))

printHash :: Cursor -> IO ()
printHash cur =
    case curFocus cur of
        P hash _ _ -> putStrLn (hashB58 hash)
        _          -> putStrLn "(current value is not a pin)"

movePin :: Cursor -> String -> IO Cursor
movePin cur rawHash =
    case lookupPin (curRoot cur) rawHash of
        PinFound fullHash val -> do
            let cur' = Cursor
                    { curRoot = curRoot cur
                    , curFocus = val
                    , curCrumbs = Crumb ("@" <> take 12 fullHash) (curFocus cur) : curCrumbs cur
                    }
            printHere cur'
            pure cur'
        PinMissing key -> do
            putStrLn $ "No pin found for hash or prefix: " <> key
            pure cur
        PinAmbiguous key matches -> do
            putStrLn $ "Ambiguous pin prefix: " <> key
            putStrLn $ "Matches " <> show (length matches) <> " pins; first matches:"
            mapM_ (putStrLn . ("  " <>)) (take 10 matches)
            pure cur

lookupPin :: Val -> String -> PinLookup
lookupPin rootVal rawHash =
    case key of
        "" -> PinMissing key
        _ ->
            case exactMatches of
                [(hash, val)] -> PinFound hash val
                _ -> case prefixMatches of
                    []            -> PinMissing key
                    [(hash, val)] -> PinFound hash val
                    matches       -> PinAmbiguous key (map fst matches)
  where
    key = stripAt rawHash
    pins = [ (hashB58 hash, val) | val@(P hash _ _) <- recursivePins rootVal ]
    exactMatches  = filter ((== key) . fst) pins
    prefixMatches = filter (isPrefixOf key . fst) pins

stripAt :: String -> String
stripAt ('@' : xs) = xs
stripAt xs         = xs

moveRoot :: Cursor -> IO Cursor
moveRoot cur = do
    let cur' = Cursor (curRoot cur) (curRoot cur) []
    printHere cur'
    pure cur'

movePath :: Cursor -> String -> IO Cursor
movePath cur path =
    case splitPath path of
        [] | startsAtRoot path -> moveRoot cur
        [] -> printHere cur >> pure cur
        parts -> do
            let startCur = if startsAtRoot path then Cursor (curRoot cur) (curRoot cur) [] else cur
            case foldM stepPath startCur parts of
                Nothing -> do
                    putStrLn $ "No such child: " <> path
                    pure cur
                Just cur' -> printHere cur' >> pure cur'

startsAtRoot :: String -> Bool
startsAtRoot ('/' : _) = True
startsAtRoot _         = False

splitPath :: String -> [String]
splitPath = filter (/= "") . go
  where
    go [] = []
    go xs =
        let (part, rest) = break (== '/') xs
        in part : case rest of
            []       -> []
            _ : rest' -> go rest'

stepPath :: Cursor -> String -> Maybe Cursor
stepPath cur "." = Just cur
stepPath cur ".." =
    case curCrumbs cur of
        [] -> Just cur
        Crumb _ parent : rest -> Just (Cursor (curRoot cur) parent rest)
stepPath cur key = do
    child <- findChild key (children (curFocus cur))
    pure Cursor
        { curRoot = curRoot cur
        , curFocus = childValue child
        , curCrumbs = Crumb (childKey child) (curFocus cur) : curCrumbs cur
        }

findChild :: String -> [Child] -> Maybe Child
findChild key = go
  where
    go [] = Nothing
    go (child : rest)
        | key == childKey child || key `elem` childAliases child = Just child
        | otherwise = go rest

children :: Val -> [Child]
children = \case
    P _ pins inner ->
        Child "inner" ["i"] "pin payload" inner
        : zipWith subPin [0 :: Int ..] pins
    L _ tag body ->
        [ Child "tag"  ["name"] "law tag"  tag
        , Child "body" []       "law body" body
        ]
    A f xs ->
        Child "head" ["fun", "f"] "app head" f
        : zipWith appArg [0 :: Int ..] (V.toList xs)
    N _ -> []
  where
    subPin ix val = Child ("sub" <> show ix)
                          ["p" <> show ix, "pin" <> show ix]
                          "sub-pin"
                          val
    appArg ix val = Child (show ix) [] "app arg" val

summary :: Val -> String
summary = \case
    P hash pins inner ->
        "Pin " <> hashB58 hash
        <> " subpins=" <> show (length pins)
        <> " inner=" <> kind inner
    L ar tag _ ->
        "Law arity=" <> show ar <> " tag=" <> preview tag
    A f xs ->
        "App args=" <> show (V.length xs) <> " head=" <> preview f
    N n ->
        "Nat " <> natPreview n

kind :: Val -> String
kind = \case
    P{} -> "Pin"
    L{} -> "Law"
    A{} -> "App"
    N{} -> "Nat"

preview :: Val -> String
preview = limit 96 . unwords . words . prettyValMulti 80

natPreview :: Natural -> String
natPreview n =
    case natShowStr n of
        Just s  -> show s
        Nothing -> show n

hashB58 :: BS8.ByteString -> String
hashB58 = BS8.unpack . Base58.encodeBase58 Base58.bitcoinAlphabet

limit :: Int -> String -> String
limit n s
    | length s <= n = s
    | n <= 3 = take n s
    | otherwise = take (n - 3) s <> "..."

padRight :: Int -> String -> String
padRight n s = s <> replicate (max 1 (n - length s)) ' '

padLeft :: Int -> String -> String
padLeft n s = replicate (max 0 (n - length s)) ' ' <> s

trim :: String -> String
trim = dropWhile isSpace . reverse . dropWhile isSpace . reverse
