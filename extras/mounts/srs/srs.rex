#import lede=sys/lede
#import req=sys/req
#import res=sys/res
#import about=sys/about
#import from=sys/from
#import now=sys/now
#import weft=sys/weft
#import tack=sys/tack
#import time=sys/types/time
#import duration=sys/types/duration
#import text=sys/types/text
#import path_type=sys/types/path

' Example grove: a minimal spaced-repetition application.
'
' Declarations:
'   @type    Explicit Foil type implementation.
'   @slot    Property identifier.
'   @role    Property constraints; synthesizes a Foil type.
'   @action  Transformation on a role, with additional arguments.
'   @norm    Constraints on the occupied shape of a namespace.
'   @sewn    Namespace transformation between two norms.
'   @tree    Concrete namespace content.
'
' Forms:
'   #meta ;            Metadata values on the declaration itself.
'   slot: rhs          A value or type requirement, by context.
'   #directive ; arg   A relationship or structural directive.
'   ! foil             Remaining body is Foil; no blank lines inside.


' Types and slots

grade =
  @type
  @slot
  #meta ;
    lede: "Review grade"
  ! foil
  +  again :
  +  hard  :
  +  good  :
  +  easy  :
  & %/again
    %/hard
    %/good
    %/easy
  + read
    \ raw=pail
    ^ maybe[grade]
    ? raw
     > value=grade/again (./some value)
     > value=grade/hard (./some value)
     > value=grade/good (./some value)
     > value=grade/easy (./some value)
    .none
  + write
    \ value=grade
    ^ pail
    ? value
     > value=grade/again value
     > value=grade/hard value
     > value=grade/good value
     > value=grade/easy value
  + contract
    | curb/of_type (^ grade)

due =
  @slot
  #meta ;
    lede: "Time next due"

interval =
  @slot
  #meta ;
    lede: "Next prompt interval"


' Object roles

recall =
  @role
  #meta ;
    lede: "Recall metadata"
  %/due: time
  %/interval: duration

card =
  @role
  #meta ;
    lede: "Review card"
  #with ; recall
  #or ;
    req: text
    about: path_type
    ' At least one must be present; both are allowed.
    ' Every present limb must satisfy its declared type.
  #opt ;
    res: text


' Review action

finish =
  @action
  #meta ;
    lede: "Finish review"
  #on ; recall
  %/grade: %/grade
  now: time
  ! foil
  \ grade=%/grade now=time rec=%/recall
  ^ %/recall
  = next_interval
    ? grade
      > .again 1
      > .hard  | div (mul rec.interval 4) 3
      > .good  | mul rec.interval 2
      > .easy  | mul rec.interval 3
  = next_due | add now next_interval
  rec.set_interval(next_interval).set_due(next_due)


' Collection norms
'
' These describe the permitted occupied paths, not just a subset
' of paths to check. Structural parent nodes may remain empty.
' Inline limbs constrain the objects at the matched paths.

cards_by_id =
  @norm
  #here ; '/[name=@tas]
  #with ; card

card_list =
  @norm
  #here; '/[name=@u]
  #with; card
  from: path_type


' Presentation: the ten soonest cards, whether overdue or upcoming.

queue =
  @sewn
  #meta ;
    lede: "Next ten cards"
  #from ; cards_by_id
  #to ; card_list
  get :
    ! foil
    + cmp
      \ left=[path myth] right=[path myth]
      ^ nat
      = [xsrc x] left
      = [ysrc y] right
      > (./some cx) (%/card/from_myth x)
        0
      > (./some cy) (%/card/from_myth y)
        0
      ' Equal due times are ordered by source identifier.
      ' The input norm guarantees one-segment paths.
      ? (eq cx.due cy.due)
        | lte_iota xsrc.at(0) ysrc.at(0)
      | le cx.due cy.due
    + push
      \ acc=[nat axal[myth]] entry=[path myth]
      ^ [nat axal[myth]]
      = [idx tree] acc
      = [src val] entry
      ' Preserve the source path relative to the input root.
      = val val.put(['sys 'from] (pails/p src))
      = tree tree.put([($u idx)] val)
      [(inc idx) tree]
    + occupied
      \ entry=[path myth]
      ^ bool
      = [key val] entry
      | eq key.len 1
    \ x=axal[myth]
    ^ axal[myth]
    = occupied
      | x.tap.keep(%/get/occupied)
    = entries
      | list/row[[path myth]]
        (occupied.stream.sort_by(%/get/cmp).take(10))
    = acc=[nat axal[myth]]
      [0 (axal/new[myth] .none)]
    = [count out]
      | row/fold[[path myth] [nat axal[myth]]]
        acc %/get/push entries
    out


' Installed namespace

"/" =
  @tree

"/cards" =
  @tree
  #like ; cards_by_id

"/cards/demo" =
  @tree
  req: "What does a Shrine name identify?"
  res: "A versioned locus of state."
  %/due: 0
  %/interval: 1

"/next" =
  @tree
  weft: %/queue
  tack: '@/y/%/cards
