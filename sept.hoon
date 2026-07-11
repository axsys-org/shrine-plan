::  %sept: Internet Protocol, version Seven
::
::    Shrine is a namespace, from a path -> data
::    /~hastuc-dibtux/chats/unit-731 :: this a chat
::    /~hastuc-dibtux/chats/unit-731/msg/~2024.1.27..10.30 :: this is a
::    message inside the chat
::
:: =>  ..ride
::  this file is required to be built against the hoon compiler plus the
::  current observed value of $pail i.e. all known namespace types. For
::  bootstrap, pail should be (pair stud *)
!:
=>
~%  %sept  ..ride  ~
::  sept: path stuff
|%
++  sept  %100
:: +|  %arvo-compat
+$  desk  @tas
+$  ship  @p
+$  mark  @tas
+$  spar  [=ship =path]
::
::  $care: Perspective on a path
::
+$  care
  $~  %x
  $?  %x  :: single node
      %y  :: single node and immediate children
      %z  :: single node and all descendants
      :: without pails or vials
      %a  :: single node (%x)
      %b  :: node and immediate children (%y)
      %c  :: node and all descendants (%z)
  ==
::
::  $hunt: Path with perspective
::
::
+$  hunt   [=care =pith]
::  $road: unfaced path
+$  road   (pole iota)
++  name
  =<  name
  |%
  +$  name  [=ship =pith]
  ++  rule
    :: ^-  _|~(nail *(like name))
    ;~(plug ;~(pfix fas sig fed:ag) stip)
  ++  en-spar
    |=  nam=name
    ^-  spar
    [ship.nam (pout pith.nam)]
  ::
  ++  en-pith
    |=  nam=name
    ^-  pith
    [p/ship.nam pith.nam]
  ++  en-tape
    |=  nam=name
    (spud (pout (en-pith nam)))
  ++  en-path
    |=  nam=name
    (pout (en-pith nam))
  ++  de-pith  |=(pith ~|(de-pith/+< (need (de-pith-soft +<))))
  ++  de-pith-soft
    |=  =pith
    ^-  (unit name)
    ?.  ?=([[%p @] *] pith)
      ~
    `[+.i.pith t.pith]
  --
++  lte-pith
  |=  [a=pith b=pith]
  ^-  ?
  ?~  a  &
  ?~  b  |
  ?.  =(i.a i.b)
    %+  lte-dime
      ?^(i.a i.a [%tas i.a])
    ?^(i.b i.b [%tas i.b])
  $(a t.a, b t.b)
++  lte-iota
  |=  [a=iota b=iota]
  ?:  =(a b)  &
  %+  lte-dime
    ?^(a a [%tas a])
  ?^(b b [%tas b])
::
++  lte-dime
  |=  [a=dime b=dime]
  ^-  ?
  ?.  =(p.a p.b)
    (aor -.a -.b)
  ?+  p.a  (lte q.a q.b)
    %rd             (lte:rd q.a q.b)
    %rh             (lte:rh q.a q.b)
    %rq             (lte:rq q.a q.b)
    %rs             (lte:rs q.a q.b)
    %s              !=(--1 (cmp:si q.a q.b))
    ?(%t %ta %tas)  (aor q.a q.b)
  ==
++  pove
  |=  i=knot
  ^-  iota
  ?^  res=(rush i spot:stip)
    u.res
  ?:  =('.y' i)
    f/&
  ?:  =('.n' i)
    f/|
  [%ta i]
::
++  pave
  |=  p=path
  ^-  pith
  (turn p pove)
::
++  pith-to-stud
  |=  p=road
  ^-  stud
  ?:  ?=([%kelvin ^ mark=@ ~] p)
    mark.p
  ?>  ?=(^ p)
  p
++  get-aura
  |=  =iota
  ?@  iota  %t
  -.iota
::  $stud: name for build system outputs
::
::    Build system outputs cannot live at arbitrary points in the
::    namespace, to allow for the build system to bootstrap itself.
::
+$  stud
  $@  @tas                                 ::  auth=urbit
  [i=iota t=pith]
++  stud-to-pith
  |=  [s=stud =term]
  ^-  pith
  ?@  s  #/std/[term]/[s]
  s
::
++  stud-to-tape
  |=  s=stud
  ^-  tape
  ?@  s  (trip s)
  %-  en-tape:pith
  s

++  stip                                                ::  typed path parser
  =<  swot
  |%
  ++  swot  |=(n=nail `(like pith)`(;~(pfix fas (more fas spot)) n))
  ::
  ++  spot
    %+  sear
      |=  a=*
      ^-  (unit iota)
      ?+  a  ~
        @      ?:(((sane %tas) a) [~ `@tas`a] ~)
        [@ @]  ((soft iota) a)
      ==
    %-  stew
    ^.  stet  ^.  limo
    :~  :-  'a'^'z'  sym
        :-  '$'      (cold [%tas %$] buc)
        :-  '0'^'9'  bisk:so
        :-  '-'      tash:so
        :-  '.'      zust:so
        :-  '~'      ;~(pfix sig ;~(pose (stag %da (cook year when:so)) crub:so (easy [%n ~])))
        :-  '\''     (stag %t qut)
        :-  '$'      (cold %$ buc)
    ==
  --
::
++  pith
  |^  $+(pith ^pith)
  ++  is-our
    |=  [our=@p pit=$]
    ?.  ?=([[%p @] *] pit)
      |
    =(+.i.pit our)
  ++  local
    |=  pit=$
    (slag 1 pit)
  ::
  ++  ship
    |=  pit=$
    ~|  no-ship-for-pith/pit
    ?>  ?=([[%p @] *] pit)
    `@p`+.i.pit
  ::
  ++  en-tape
    |=  pit=$
    (spud (pout pit))
  ++  dif
    |=  [a=$ b=$]
    |-  ^+  a
    ?~  a  b
    ?~  b  a
    ?.  =(i.a i.b)
      a
    $(a t.a, b t.b)
  ++  sub
    |=  [from=$ del=$]
    ~|  pith-sub/[from del]
    !.
    |-  ^+  from
    ?~  del  from
    ?>  ?=(^ from)
    ?>  =(i.del i.from)
    $(del t.del, from t.from)
  ::
  ++  en-cord
    |=  pit=$
    (spat (pout pit))
  ++  de-cord
    |=  pit=@t
    (pave (stab pit))
  ::
  ++  prefix
    =|  res=$
    |=  [long=$ curt=$]
    ^-  (unit _res)
    ?~  curt  `(flop res)
    ?~  long  ~
    ?.  =(i.long i.curt)
      ~
    $(long t.long, curt t.curt, res [i.long res])
  ++  is-prefix
    |=  [long=$ curt=$]
    !=(~ (prefix long curt))
  ::
  ++  suffix
    |=  [long=$ curt=$]
    ^-  _curt
    ?~  curt
      long
    ?~  long
      ~
    $(curt t.curt, long t.long)
  ++  sor
    |=  [a=$ b=$]
    (lte (lent a) (lent b))
  --
++  duct  (list pith)


--  =>
::  sept: ordered map + axal
|%
++  uon
  |$  [val]
  ((mop iota val) lte-iota)
++  aon
  ~/  %aon
  =|  a=((mop iota *) lte-iota)
  |@
  ++  raw  ((on iota *) lte-iota)
  +$  item  [key=iota val]
  +$  val  ,_?>(?=(^ a) +.n.a)
  +$  tre   (tree item)
  ::  +apt: verify horizontal and vertical orderings
  ::
  ++  apt
    ~/  %apt
    =|  [l=(unit iota) r=(unit iota)]
    |-  ^-  ?
    ::  empty tree is valid
    ::
    ?~  a  %.y
    ::  nonempty trees must maintain several criteria
    ::
    ?&  ::  if .n.a is left of .u.l, assert horizontal comparator
        ::
        ?~(l %.y (lte-iota key.n.a u.l))
        ::  if .n.a is right of .u.r, assert horizontal comparator
        ::
        ?~(r %.y (lte-iota u.r key.n.a))
        ::  if .a is not leftmost element, assert vertical order between
        ::  .l.a and .n.a and recurse to the left with .n.a as right
        ::  neighbor
        ::
        ?~(l.a %.y &((mor key.n.a key.n.l.a) $(a l.a, l `key.n.a)))
        ::  if .a is not rightmost element, assert vertical order
        ::  between .r.a and .n.a and recurse to the right with .n.a as
        ::  left neighbor
        ::
        ?~(r.a %.y &((mor key.n.a key.n.r.a) $(a r.a, r `key.n.a)))
    ==

  ++  run
    ~/  %run
    |*  fun=gate
    |-
    ?~  a  a
    [n=[key.n.a (fun val.n.a)] l=$(a l.a) r=$(a r.a)]
  ++  gas
    ~/  %gas
    |*  b=(list [p=* q=*])
    =>  .(b `(list _?>(?=(^ a) n.a))`b)
    |-  ^+  a
    ?~  b
      a
    $(b t.b, a (put i.b))
  ::
  ++  rut
    ~/  %rut
    |*  fun=gate
    |-  ^+  a
    ?~  a  a
    [n=[key.n.a (fun key.n.a val.n.a)] l=$(a l.a) r=$(a r.a)]
  ::
  ++  uno
    :: ~/  %uno
    |*  b=_a
    |*  meg=$-([* * *] *)
    |-  ^+  a
    ?~  b  a
    ?~  a  b
    ?:  =(key.n.a key.n.b)
      [n=[key=key.n.a val=(meg key.n.a val.n.a val.n.b)] l=$(a l.a, b l.b) r=$(a r.a, b r.b)]
    ?:  (mor key.n.a key.n.b)
      ?:  (lte-iota key.n.b key.n.a)
        $(l.a $(a l.a, r.b ~), b r.b)
      $(r.a $(a r.a, l.b ~), b l.b)
    ?:  (lte-iota key.n.a key.n.b)
      $(l.b $(b l.b, r.a ~), a r.a)
    $(r.b $(b r.b, l.a ~), a l.a)
  ::
  ++  uni
    :: ~/  %uni
    |*  b=_a
    |-  ^+  b
    ?~  b  a
    ?~  a  b
    ?:  =(key.n.a key.n.b)
      [n=n.b l=$(a l.a, b l.b) r=$(a r.a, b r.b)]
    ?:  (mor key.n.a key.n.b)
      ?:  (lte-iota key.n.b key.n.a)
        $(l.a $(a l.a, r.b ~), b r.b)
      $(r.a $(a r.a, l.b ~), b l.b)
    ?:  (lte-iota key.n.a key.n.b)
      $(l.b $(b l.b, r.a ~), a r.a)
    $(r.b $(b r.b, l.a ~), a l.a)
  ::  +put: ordered item insert
  ::
  ++  put
    |*  [b=iota c=*]
    |-  ^+  a
    ::  base case: replace null with single-item tree
    ::
    ?~  a  [n=[b c] l=~ r=~]
    ::  base case: overwrite existing .key with new .val
    ::
    ?:  =(key.n.a b)  a(val.n c)
    ::  if item goes on left, recurse left then rebalance vertical order
    ::
    ?:  (lte-iota b key.n.a)
      =/  l  $(a l.a)
      ?>  ?=(^ l)
      ?:  (mor key.n.a key.n.l)
        a(l l)
      l(r a(l r.l))
    ::  item goes on right; recurse right then rebalance vertical order
    ::
    =/  r  $(a r.a)
    ?>  ?=(^ r)
    ?:  (mor key.n.a key.n.r)
      a(r r)
    r(l a(r l.r))
  ::  +ram: produce tail (rightmost item) or null
  ::
  ++  ram
    ^-  (unit item)
    ?~  a    ~
    |-
    ?~  r.a  `n.a
    $(a r.a)
  ::  +rem: produce tail of given aura (rightmost item) or null
  ::
  ++  rem
    =|  have=(unit @)
    |=  =aura
    ^+  have
    ?~  a    ~
    =?  have  =((get-aura key.n.a) aura)
      ?@  key.n.a   `key.n.a
      `+.key.n.a
    ?~  r.a  have
    $(a r.a)

  ::  +pry: produce head (leftmost item) or null
  ::
  ++  pry
    ^-  (unit item)
    ?~  a    ~
    |-
    ?~  l.a  `n.a
    $(a l.a)

  ++  tap
    =<  $
    ~/  %tap
    =|  b=(list item)
    |.  ^+  b
    ?~  a  b
    $(a l.a, b [n.a $(a r.a)])
  ::  +get: get val at key or return ~
  ::
  ++  get
    ~/  %get
    |=  b=iota
    ^-  (unit val)
    ?~  a  ~
    ?:  =(b key.n.a)
      `val.n.a
    ?:  (lte-iota b key.n.a)
      $(a l.a)
    $(a r.a)
  ++  got
    |=  b=iota
    (need (get b))
  ++  gut
    |*  [b=iota c=*]
    (fall (get b) c)


  ::  +del: delete .key from .a if it exists, producing value iff deleted
  ::
  ++  del
    ~/  %del
    |*  b=iota
    |-  ^-  [(unit val) (tree item)]
    ?~  a  [~ ~]
    ::  we found .key at the root; delete and rebalance
    ::
    ?:  =(b key.n.a)
      [`val.n.a nip]
    ::  recurse left or right to find .key
    ::
    ?:  (lte-iota b key.n.a)
      =+  [found lef]=$(a l.a)
      [found a(l lef)]
    =+  [found rig]=$(a r.a)
    [found a(r rig)]
  ++  nip
    ~/  %nip
    |-  ^-  (tree item)
    ?>  ?=(^ a)
    ::  delete .n.a; merge and balance .l.a and .r.a
    ::
    |-  ^-  (tree item)
    ?~  l.a  r.a
    ?~  r.a  l.a
    ?:  (mor key.n.l.a key.n.r.a)
      l.a(r $(l.a r.l.a))
    r.a(l $(r.a l.r.a))
  --
++  axal
  |$  [item]
  [fil=(unit item) kid=(uon $)]

++  print-axal
  |=  a=(axal)
  ^-  (list tape)
  %-  zing
  %+  turn  ~(tap of a)
  |=  [k=pith v=*]
  ^-  (list tape)
  =/  is-cell  ?:(?=(^ v) "cell" "atom")
  :~  "key: {(trip (spat (pout k)))}"
      "val: {is-cell}"
  ==


++  of
  ~/  %of
  =|  fat=(axal)
  |@
  ++  apt
    |-  ^-  ?
    =*  loop  $
    ?&
        ~(apt aon kid.fat)
        ::
        %+  levy  ~(tap aon kid.fat)
        |*  [k=iota v=_fat]
        loop(fat v)
    ==

  :: ++  on  ((^on iota ) lte-iota)
  ::  XX: strange moist
  ++  set
    ~/  %set
    |*  [pax=pith ls=_kid.fat]
    ^+  fat
    :: =/  l  ~(tap aon ls)
    %+  rep  pax
    =.  fat  (dip pax)
    :: |-
    =.  kid.fat  (~(uni aon ls) kid.fat)
    fat

  ::  XX: TODO: clarify whether ram/pry get lowest existing, or lowest
  ::  subtree
  ++  pry
    ~/  %pry
    |*  pax=pith
    ^-  (unit [key=iota val=_?>(?=(^ fil.fat) u.fil.fat)])
    =/  res=(unit [key=iota val=_fat])
      ~(pry aon kid:(dip pax))
    ?~  res
      ~
    ?~  fil.val.u.res
      ~
    [~ u=[key=key.u.res val=u.fil.val.u.res]] ::
  ::  XX: TODO: clarify whether ram/pry get lowest existing, or lowest
  ::  subtree
  ++  pry-path
    ~/  %pry
    =|  here=pith
    |*  pax=pith
    ^-  (unit [pith:t _?>(?=(^ fil.fat) u.fil.fat)])
    =/  res=(unit [key=iota val=_fat])
      ~(pry aon kid:(dip pax))
    ?~  res
      ~
    ?~  fil.val.u.res
      $(here (snoc here key.u.res), fat val.u.res)
    [~ u=[here u.fil.val.u.res]]
  ::
  ++  ram
    ~/  %ram
    |*  pax=pith
    ^-  (unit [key=iota val=_?>(?=(^ fil.fat) u.fil.fat)])
    =/  res=(unit [key=iota val=_fat])
      ~(ram aon kid:(dip pax))
    ?~  res
      ~
    ?~  fil.val.u.res
      ~
    [~ u=[key=key.u.res val=u.fil.val.u.res]] ::
  ++  rim
    ~/  %ram
    |=  pax=pith
    ^-  @ud
    =/  res=(unit [key=iota val=_fat])
      ~(ram aon kid:(dip pax))
    ?~  res  0
    ?@  -.u.res  `@ud`-.u.res
    `@ud`->.u.res
  ::
  ++  rot
    (need fil.fat)
  ++  run
    ~/  %run
    |*  b=gate
    |-
    =+  c=`(axal _?>(?=(^ fil.fat) (b u.fil.fat)))`[~ ~]
    ^+  c
    =*  loop  $
    =?  fil.c  ?=(^ fil.fat)
      `(b u.fil.fat)
    %=    c
        kid
      %-  ~(run aon kid.fat)
      |=  ax=_fat
      ^+  c
      loop(fat ax)
    ==
  ::
  ++  wyt
    |-  ^-  @ud
    =*  loop  $
    %+  add
      ?~(fil.fat 0 1)
    %+  roll  ~(val by kid.fat)
    |*  [ax=_fat out=@ud]
    (add out loop(fat ax))
  ::
  ++  uni
    ~/  %uni
    |*  taf=_fat
    |-  ^+  fat
    =*  loop  $
    =?  fil.fat  =(~ fil.fat)
      fil.taf
    :-  ?~(fil.fat fil.taf fil.fat)
    %-  (~(uno aon kid.fat) kid.taf)
    |=  [k=iota l=_fat r=_taf]
    ^+  fat
    loop(fat l, taf r)
  ::
  ++  view
    =|  res=(map pith _?>(?=(^ fil.fat) u.fil.fat))
    |=  [=care pax=pith]
    =.  fat  (dip pax)
    =?  res  ?=(^ fil.fat)
     (~(put by res) ~ u.fil.fat)
    ?-  care
      %x  res
      %y  =.(fat snip (~(uni by res) tar))
      %z  (~(uni by res) tar)
    ==
  ++  jab-til
    |*  [pax=pith fun=$-(* *) gat=$-(* *)]
    ^+  fat
    ?~  pax
      ?~  fil.fat
        fat
      fat(fil `(gat u.fil.fat))
    =?  fil.fat  ?=(^ fil.fat)
      `(fun u.fil.fat)
    fat(kid (~(put aon kid.fat) i.pax $(fat (~(got aon kid.fat) i.pax), pax t.pax)))

  ::
  ++  anc-jab
    |*  [pax=pith fun=$-(* *)]
    ^+  fat
    ?~  pax
      fat
    =?  fil.fat  ?=(^ fil.fat)
      `(fun u.fil.fat)
    fat(kid (~(put aon kid.fat) i.pax $(fat (~(got aon kid.fat) i.pax), pax t.pax)))

  ::
  ++  anc
    =|  res=(list pith)
    =|  cur=pith
    |=  pax=pith
    ^-  (^set pith)
    ?~  pax
      (~(gas in *(^set pith)) res)
    =?  res  ?=(^ fil.fat)
      [cur res]
    $(fat (~(got aon kid.fat) i.pax), pax t.pax, cur (snoc cur i.pax))
  ++  parent
    ~/  %parent
    |=  pax=pith
    =|  res=(unit pith)
    =|  cur=pith
    |-  ^+  res
    ?~  pax
      res
    =?  res  ?=(^ fil.fat)
      `cur
    =/  nex  (~(get aon kid.fat) i.pax)
    ?~  nex
      res
    $(fat u.nex, pax t.pax, cur (snoc cur i.pax))
  ++  snip
    |-  ^+  fat
    =*  loop  $
    %_    fat
        kid
      %-  ~(run aon kid.fat)
      |=  f=_fat
      ?^  fil.f
        [`u.fil.f ~]
      loop(fat f)
    ==
  ::
  ++  kid
    ~/  %kid
    |=  pax=pith
    ^-  (map pith _?>(?=(^ fil.fat) u.fil.fat))
    =.  fat  (dip pax)
    =.  fat  snip
    =.  fil.fat  ~
    tar
  ::
  ::
  ++  del
    ~/  %del
    |=  pax=pith
    ^+  fat
    ?~  pax  [~ kid.fat]
    =/  kid  (~(get aon kid.fat) i.pax)
    ?~  kid  fat
    fat(kid (~(put aon kid.fat) i.pax $(fat u.kid, pax t.pax)))
  ++  del-get
    ~/  %del
    |=  pax=pith
    ^+  [fil.fat fat]
    ?~  pax  [fil.fat [~ kid.fat]]
    =/  kid  (~(get aon kid.fat) i.pax)
    ?~  kid  [~ fat]
    fat(kid (~(put aon kid.fat) i.pax $(fat u.kid, pax t.pax)))
  ::
  ++  rip
    ~/  %rip
    |=  pax=pith
    ^+  [fat fat]
    [(dip pax) (rep pax [~ ~])]
  ::
  ::  Descend to the axal at this path
  ::
  ++  dip
    ~/  %dip
    |=  pax=pith
    ^+  fat
    ?~  pax  fat
    =/  kid  (~(get aon kid.fat) i.pax)
    ?~  kid  [~ ~]
    $(fat u.kid, pax t.pax)
  ::
  ++  gas
    ~/  %gas
    |*  lit=(list (pair pith _?>(?=(^ fil.fat) u.fil.fat)))
    |-  ^+  fat
    ?~  lit  fat
    $(fat (put p.i.lit q.i.lit), lit t.lit)
  ++  got
    ~/  %got
    |=  pax=pith
    ~|  missing-room/pax
    (need (get pax))
  ++  gut
    ~/  %gut
    |*  [pax=pith dat=*]
    ::  =>  .(dat `_?>(?=(^ fil.fat) u.fil.fat)`dat, pax `pith`pax)
    (fall (get pax) dat)
  ::
  ++  get
    ~/  %get
    |=  pax=pith
    fil:(dip pax)
  ::  Fetch file at longest existing prefix of the path
  ::
  ++  fit
    ~/  %fit
    |=  pax=pith
    ^+  [pax fil.fat]
    ?~  pax  [~ fil.fat]
    =/  kid  (~(get aon kid.fat) i.pax)
    ?~  kid  [pax fil.fat]
    =/  low  $(fat u.kid, pax t.pax)
    ?~  +.low
      [pax fil.fat]
    low
  ::
  ++  has
    ~/  %has
    |=  pax=pith
    !=(~ (get pax))
  ::
  ++  nonempty
    |=  pax=pith
    ^-  ?
    =.  fat  (dip pax)
    |-  =*  outer  $
    ?^  fil.fat  &
    =/  kid  ~(tap aon kid.fat)
    |-  =*  inner  $
    ?~  kid  |
    ?:  outer(fat +.i.kid)  &
    inner(kid t.kid)

  ::  Delete subtree
  ::
  ++  lop
    ~/  %lop
    |*  pax=pith
    |-  ^+  fat
    ?~  pax  fat
    ?~  t.pax  fat(kid +:(~(del aon kid.fat) i.pax))
    =/  kid  (~(get aon kid.fat) i.pax)
    ?~  kid  fat
    fat(kid (~(put aon kid.fat) i.pax $(fat u.kid, pax t.pax)))
  ++  rep
    ~/  %rep
    |*  [pax=pith fit=_fat]
    |-  ^+  fat
    ?~  pax  fit
    =/  kid  (~(gut aon kid.fat) i.pax ^+(fat [~ ~]))
    fat(kid (~(put aon kid.fat) i.pax $(fat kid, pax t.pax)))
  ::
  ++  jab
    ~/  %jab
    |*  [pax=pith fun=$-(_?>(?=(^ fil.fat) u.fil.fat) _?>(?=(^ fil.fat) u.fil.fat))]
    ^+  fat
    =/  kid  (got pax)
    (put pax (fun kid))
  ::
  ++  put
    ~/  %put
    |*  [pax=pith dat=*]
    ^+  fat
    =>  .(dat `_?>(?=(^ fil.fat) u.fil.fat)`dat, pax `pith`pax)
    |-  ^+  fat
    ?~  pax  fat(fil `dat)
    =/  kid  (~(gut aon kid.fat) i.pax ^+(fat [~ ~]))
    fat(kid (~(put aon kid.fat) i.pax $(fat kid, pax t.pax)))
  ::
  ++  rut
    =|  here=pith
    ~/  %rut
    |*  fun=$-([pith _?>(?=(^ fil.fat) u.fil.fat)] _?>(?=(^ fil.fat) u.fil.fat))
    ^+  fat
    %=  fat
      fil  ?~(fil.fat ~ `(fun here u.fil.fat))
      kid  (~(rut aon kid.fat) |=([iot=iota f=_fat] ^$(here (snoc here iot), fat f)))
    ==
  ++  rum
    ~/  %rum
    |*  fun=$-(_?>(?=(^ fil.fat) u.fil.fat) _fil.fat)
    ^+  fat
    %=  fat
      fil  ?~(fil.fat ~ (fun u.fil.fat))
      kid  (~(rut aon kid.fat) |=([iot=iota f=_fat] ^$(fat f)))
    ==
  ::
  ++  val
    ^-  (list _?>(?=(^ fil.fat) u.fil.fat))
    (turn tap tail)
  ::
  ++  key
    ^-  (list pith)
    (turn tap head)
  ::
  ++  tap
    =|  pax=pith
    =|  out=(list (pair pith _?>(?=(^ fil.fat) u.fil.fat)))
    |-  ^+   out
    =?  out  ?=(^ fil.fat)  :_(out [pax u.fil.fat])
    =/  kid=(list (pair iota (axal _?>(?=(^ fil.fat) u.fil.fat))))
      ~(tap aon kid.fat)
    |-  ^+   out
    ~!  out
    ?~  kid  out
    %=  $
      kid  t.kid
      out  ^$(pax (weld pax /[p.i.kid]), fat q.i.kid)
    ==

  ++  sap
    %+  sort  tap
    |*  [[a=pith *] [b=pith *]]
    (sort:pith a b)
  ++  aap
    ^-  (list [pith _?>(?=(^ fil.fat) u.fil.fat)])
    %+  sort  tap
    |*  [[a=pith *] [b=pith *]]
    (lte-pith a b)
  ::  Serialize to map
  ::
  ++  tar
    (~(gas by *(map pith _?>(?=(^ fil.fat) u.fil.fat))) tap)
  --
::
::  +mop: constructs and validates ordered ordered map based on key,
::  val, and comparator gate
::
++  mop
  |*  [key=mold value=mold]
  |=  ord=$-([key key] ?)
  |=  a=*
  =/  b  ;;((tree [key=key val=value]) a)
  ?>  (apt:((on key value) ord) b)
  b
::  +on: treap with user-specified horizontal order, ordered-map
::
::  WARNING: ordered-map will not work properly if two keys can be
::  unequal under noun equality but equal via the compare gate
::
++  on
  ~%  %on  ..ride  ~
  |*  [key=mold val=mold]
  =>  |%
      +$  item  [key=key val=val]
      --
  ::  +compare: item comparator for horizontal order
  ::
   ~%  %comp  +>+  ~
  |=  compare=$-([key key] ?)
   ~%  %core    +  ~
  |%
  ++  new  %foo
  ::  +all: apply logical AND boolean test on all values
  ::
  ++  all
    ~/  %all
    |=  [a=(tree item) b=$-(item ?)]
    ^-  ?
    |-
    ?~  a
      &
    ?&((b n.a) $(a l.a) $(a r.a))
  ::  +any: apply logical OR boolean test on all values
  ::
  ++  any
    ~/  %any
    |=  [a=(tree item) b=$-(item ?)]
    |-  ^-  ?
    ?~  a
      |
    ?|((b n.a) $(a l.a) $(a r.a))
  ::  +apt: verify horizontal and vertical orderings
  ::
  ++  apt
    ~/  %apt
    |=  a=(tree item)
    =|  [l=(unit key) r=(unit key)]
    |-  ^-  ?
    ::  empty tree is valid
    ::
    ?~  a  %.y
    ::  nonempty trees must maintain several criteria
    ::
    ?&  ::  if .n.a is left of .u.l, assert horizontal comparator
        ::
        ?~(l %.y (compare key.n.a u.l))
        ::  if .n.a is right of .u.r, assert horizontal comparator
        ::
        ?~(r %.y (compare u.r key.n.a))
        ::  if .a is not leftmost element, assert vertical order between
        ::  .l.a and .n.a and recurse to the left with .n.a as right
        ::  neighbor
        ::
        ?~(l.a %.y &((mor key.n.a key.n.l.a) $(a l.a, l `key.n.a)))
        ::  if .a is not rightmost element, assert vertical order
        ::  between .r.a and .n.a and recurse to the right with .n.a as
        ::  left neighbor
        ::
        ?~(r.a %.y &((mor key.n.a key.n.r.a) $(a r.a, r `key.n.a)))
    ==
  ::  +bap: convert to list, right to left
  ::
  ++  bap
    ~/  %bap
    |=  a=(tree item)
    ^-  (list item)
    =|  b=(list item)
    |-  ^+  b
    ?~  a  b
    $(a r.a, b [n.a $(a l.a)])
  ::  +del: delete .key from .a if it exists, producing value iff deleted
  ::
  ++  del
    ~/  %del
    |=  [a=(tree item) =key]
    ^-  [(unit val) (tree item)]
    ?~  a  [~ ~]
    ::  we found .key at the root; delete and rebalance
    ::
    ?:  =(key key.n.a)
      [`val.n.a (nip a)]
    ::  recurse left or right to find .key
    ::
    ?:  (compare key key.n.a)
      =+  [found lef]=$(a l.a)
      [found a(l lef)]
    =+  [found rig]=$(a r.a)
    [found a(r rig)]
  ::  +dip: stateful partial inorder traversal
  ::
  ::    Mutates .state on each run of .f.  Starts at .start key, or if
  ::    .start is ~, starts at the head.  Stops when .f produces .stop=%.y.
  ::    Traverses from left to right keys.
  ::    Each run of .f can replace an item's value or delete the item.
  ::
  ++  dip
    ~/  %dip
    |*  state=mold
    |=  $:  a=(tree item)
            =state
            f=$-([state item] [(unit val) ? state])
        ==
    ^+  [state a]
    ::  acc: accumulator
    ::
    ::    .stop: set to %.y by .f when done traversing
    ::    .state: threaded through each run of .f and produced by +abet
    ::
    =/  acc  [stop=`?`%.n state=state]
    =<  abet  =<  main
    |%
    ++  this  .
    ++  abet  [state.acc a]
    ::  +main: main recursive loop; performs a partial inorder traversal
    ::
    ++  main
      ^+  this
      ::  stop if empty or we've been told to stop
      ::
      ?:  =(~ a)  this
      ?:  stop.acc  this
      ::  inorder traversal: left -> node -> right, until .f sets .stop
      ::
      =.  this  left
      ?:  stop.acc  this
      =^  del  this  node
      =?  this  !stop.acc  right
      =?  a  del  (nip a)
      this
    ::  +node: run .f on .n.a, updating .a, .state, and .stop
    ::
    ++  node
      ^+  [del=*? this]
      ::  run .f on node, updating .stop.acc and .state.acc
      ::
      ?>  ?=(^ a)
      =^  res  acc  (f state.acc n.a)
      ?~  res
        [del=& this]
      [del=| this(val.n.a u.res)]
    ::  +left: recurse on left subtree, copying mutant back into .l.a
    ::
    ++  left
      ^+  this
      ?~  a  this
      =/  lef  main(a l.a)
      lef(a a(l a.lef))
    ::  +right: recurse on right subtree, copying mutant back into .r.a
    ::
    ++  right
      ^+  this
      ?~  a  this
      =/  rig  main(a r.a)
      rig(a a(r a.rig))
    --
  ::  +gas: put a list of items
  ::
  ++  gas
    ~/  %gas
    |=  [a=(tree item) b=(list item)]
    ^-  (tree item)
    ?~  b  a
    $(b t.b, a (put a i.b))
  ::  +get: get val at key or return ~
  ::
  ++  get
    ~/  %get
    |=  [a=(tree item) b=key]
    ^-  (unit val)
    ?~  a  ~
    ?:  =(b key.n.a)
      `val.n.a
    ?:  (compare b key.n.a)
      $(a l.a)
    $(a r.a)
  ::  +got: need value at key
  ::
  ++  got
    |=  [a=(tree item) b=key]
    ^-  val
    (need (get a b))
  ::  +has: check for key existence
  ::
  ++  has
    ~/  %has
    |=  [a=(tree item) b=key]
    ^-  ?
    !=(~ (get a b))
  ::  +lot: take a subset range excluding start and/or end and all elements
  ::  outside the range
  ::
  ++  lot
    ~/  %lot
    |=  $:  tre=(tree item)
            start=(unit key)
            end=(unit key)
        ==
    ^-  (tree item)
    |^
    ?:  ?&(?=(~ start) ?=(~ end))
      tre
    ?~  start
      (del-span tre %end end)
    ?~  end
      (del-span tre %start start)
    ?>  (compare u.start u.end)
    =.  tre  (del-span tre %start start)
    (del-span tre %end end)
    ::
    ++  del-span
      |=  [a=(tree item) b=?(%start %end) c=(unit key)]
      ^-  (tree item)
      ?~  a  a
      ?~  c  a
      ?-  b
          %start
        ::  found key
        ?:  =(key.n.a u.c)
          (nip a(l ~))
        ::  traverse to find key
        ?:  (compare key.n.a u.c)
          ::  found key to the left of start
          $(a (nip a(l ~)))
        ::  found key to the right of start
        a(l $(a l.a))
      ::
          %end
        ::  found key
        ?:  =(u.c key.n.a)
          (nip a(r ~))
        ::  traverse to find key
        ?:  (compare key.n.a u.c)
          :: found key to the left of end
          a(r $(a r.a))
        :: found key to the right of end
        $(a (nip a(r ~)))
      ==
    --
  ::  +nip: remove root; for internal use
  ::
  ++  nip
    ~/  %nip
    |=  a=(tree item)
    ^-  (tree item)
    ?>  ?=(^ a)
    ::  delete .n.a; merge and balance .l.a and .r.a
    ::
    |-  ^-  (tree item)
    ?~  l.a  r.a
    ?~  r.a  l.a
    ?:  (mor key.n.l.a key.n.r.a)
      l.a(r $(l.a r.l.a))
    r.a(l $(r.a l.r.a))
  ::
  ::  +pop: produce .head (leftmost item) and .rest or crash if empty
  ::
  ++  pop
    ~/  %pop
    |=  a=(tree item)
    ^-  [head=item rest=(tree item)]
    ?~  a    !!
    ?~  l.a  [n.a r.a]
    =/  l  $(a l.a)
    :-  head.l
    ::  load .rest.l back into .a and rebalance
    ::
    ?:  |(?=(~ rest.l) (mor key.n.a key.n.rest.l))
      a(l rest.l)
    rest.l(r a(r r.rest.l))
  ::  +pry: produce head (leftmost item) or null
  ::
  ++  pry
    ~/  %pry
    |=  a=(tree item)
    ^-  (unit item)
    ?~  a    ~
    |-
    ?~  l.a  `n.a
    $(a l.a)
  ::  +put: ordered item insert
  ::
  ++  put
    ~/  %put
    |=  [a=(tree item) =key =val]
    ^-  (tree item)
    ::  base case: replace null with single-item tree
    ::
    ?~  a  [n=[key val] l=~ r=~]
    ::  base case: overwrite existing .key with new .val
    ::
    ?:  =(key.n.a key)  a(val.n val)
    ::  if item goes on left, recurse left then rebalance vertical order
    ::
    ?:  (compare key key.n.a)
      =/  l  $(a l.a)
      ?>  ?=(^ l)
      ?:  (mor key.n.a key.n.l)
        a(l l)
      l(r a(l r.l))
    ::  item goes on right; recurse right then rebalance vertical order
    ::
    =/  r  $(a r.a)
    ?>  ?=(^ r)
    ?:  (mor key.n.a key.n.r)
      a(r r)
    r(l a(r l.r))
  ::  +ram: produce tail (rightmost item) or null
  ::
  ++  ram
    ~/  %ram
    |=  a=(tree item)
    ^-  (unit item)
    ?~  a    ~
    |-
    ?~  r.a  `n.a
    $(a r.a)
  ::  +run: apply gate to transform all values in place
  ::
  ++  run
    ~/  %run
    |*  [a=(tree item) b=$-(val *)]
    |-
    ?~  a  a
    [n=[key.n.a (b val.n.a)] l=$(a l.a) r=$(a r.a)]
  ::  +tab: tabulate a subset excluding start element with a max count
  ::
  ++  tab
    ~/  %tab
    |=  [a=(tree item) b=(unit key) c=@]
    ^-  (list item)
    |^
    (flop e:(tabulate (del-span a b) b c))
    ::
    ++  tabulate
      |=  [a=(tree item) b=(unit key) c=@]
      ^-  [d=@ e=(list item)]
      ?:  ?&(?=(~ b) =(c 0))
        [0 ~]
      =|  f=[d=@ e=(list item)]
      |-  ^+  f
      ?:  ?|(?=(~ a) =(d.f c))  f
      =.  f  $(a l.a)
      ?:  =(d.f c)  f
      =.  f  [+(d.f) [n.a e.f]]
      ?:(=(d.f c) f $(a r.a))
    ::
    ++  del-span
      |=  [a=(tree item) b=(unit key)]
      ^-  (tree item)
      ?~  a  a
      ?~  b  a
      ?:  =(key.n.a u.b)
        r.a
      ?:  (compare key.n.a u.b)
        $(a r.a)
      a(l $(a l.a))
    --
  ::  +tap: convert to list, left to right
  ::
  ++  tap
    ~/  %tap
    |=  a=(tree item)
    ^-  (list item)
    =|  b=(list item)
    |-  ^+  b
    ?~  a  b
    $(a l.a, b [n.a $(a r.a)])
  ::  +uni: unify two ordered maps
  ::
  ::    .b takes precedence over .a if keys overlap.
  ::
  ++  uni
    ~/  %uni
    |=  [a=(tree item) b=(tree item)]
    ^-  (tree item)
    ?~  b  a
    ?~  a  b
    ?:  =(key.n.a key.n.b)
      [n=n.b l=$(a l.a, b l.b) r=$(a r.a, b r.b)]
    ?:  (mor key.n.a key.n.b)
      ?:  (compare key.n.b key.n.a)
        $(l.a $(a l.a, r.b ~), b r.b)
      $(r.a $(a r.a, l.b ~), b l.b)
    ?:  (compare key.n.a key.n.b)
      $(l.b $(b l.b, r.a ~), a r.a)
    $(r.b $(b r.b, l.a ~), a l.a)
  ::  +wyt: measure size
  ::
  ++  wyt
    ~/  %wyt
    |=  a=(tree item)
    ^-  @ud
    ?~(a 0 +((add $(a l.a) $(a r.a))))
  --
--  =>
::  sept: core types
::
::    this does not include any types that include $pail, due to those
::    types needing to be
|%
::
::  $ever: Total shrub version
::
::    .exe is incremented only when the shrub itself changes i.e. it
::    versions the %x care
::    .why is incremented when the shrub or any of its children changes
::    i.e. it versions the %y care
::    .zed is incremened when the shrub of any of its descendants change
::
::  $lock: Data and shape numbers
::
::     .p is the data version
::     .q is the shape version
+$  lock  (pair @ud @ud)
++  ever
  =<  ever
  |%
  ++  get-case
    |=  [=care =ever]
    ^-  @ud
    ?-  care
      ?(%x %a)  p.exe.ever
      ?(%y %b)  p.why.ever
      ?(%z %c)  p.zed.ever
    ==
  +$  ever
    $:  exe=lock :: %x <- file version
        why=lock :: %y <- folder version
        zed=lock :: %z <- subtree version
      ::
        ::shrub-life=@ud :: 3 (xx: deprecated)
        ::ship-life=@ud :: 6
        ::ship-rift=@ud :: 9
      ::
        ::block-height=@ud
      ::

        =time
        block=@ud
    ==
  --
+$  once  [=care q=case]               :: version *specifier*
+$  seek  [?(%x %y %z) p=?]            :: change notification,
+$  hash   @uvH                        :: BLAKE3 hash
+$  seal   @uvH                        :: signature
+$  oath  (pair hash seal)             :: Authentication of a namespace binding
+$  case  @ud                          :: number, as version
::  $bolt: sync permissions
+$  bolt
  $%  [%open ~]   :: public
      [%shut p=@ud] :: encrypted with key
      [%chum p=ship] :: diffie-hellman (XX: firm up ship vs. pith)
      [%stop ~]  :: private
  ==
+$  view
  $:  over=[=case =pith]
      =hunt
  ==

::  $mode: Kind of change
+$  mode  $~(%add ?(%add %dif %del))
++  mode-to-char
  |=  =mode
  ?-  mode
    %add  '+'
    %dif  ':'
    %del  '-'
  ==
::
::  $aeon: Metadata for a bindinng
+$  aeon  (pair ever oath)
+$  loot  [case=@ud =mode]
::  $myth: tale, but network-safe
::
+$  myth  (map slot vial)
::  $book: saga, but network-safe
+$  book  (pair aeon myth)
::  $vial: pail, but network-safe
+$  vial  (pair path *)
+$  yuga  (axal book)
+$  huge  (unit yuga)
+$  crew  (map term pith)              :: dependency injection map
+$  fans  (jug care pith)              :: subscriber map
++  slot
  =<  slot
  |%
  +$  slot  pith
  ::  +content: the "primary" item at this path
  ::
  ::    TODO: commentary
  ++  content    /sys/slot/content
  ++  auth       /sys/slot/auth
  ::  +src: textual source
  ::
  ::    ought to be suitable for sending over the network
  ++  src        /sys/slot/src
  ::  +built: built code
  ::
  ::    only use for code that is not vased
  ++  built      /sys/slot/built
  ::  +type: type
  ++  type       /sys/slot/type
  ::  +vase: built hoon+nock formula
  ++  vase       /sys/slot/vase
  ::  +card: work item
  ++  card       /sys/slot/card
  ++  help       /sys/slot/help
  ::  +lede: a title for this part of the namespace
  ::
  ::
  ++  lede       /sys/slot/lede
  ::  +kook: rules for the evolution of this path
  ::
  ::     if present, must be a (list pith:t).
  ::     if absent, list is assumed to be empty, and the path is
  ::     "unconstrained"
  ::
  ++  kook       /sys/slot/kook
  ++  crew       /sys/slot/crew
  ++  fans       /sys/slot/fans
  ++  req        /std/slot/req
  ++  res        /std/slot/res
  ++  clan       /sys/slot/clan
  ++  cant       /sys/slot/cant
  ++  icon       /sys/slot/icon
  ++  author       /sys/slot/author
  ++  prodigy      /sys/slot/prodigy
  ++  unreads      /sys/slot/unreads
  ++  prov         /sys/slot/prov
  ++  action      /sys/slot/action
  ++  like        /sys/slot/like
  ++  ast        /sys/slot/ast
  --

--  =>
::  sept: variant core types
::
::    These are the types that close over the type of $pail. This core
::    is required to be wet in order to allows the value of pail to be
::    changed at runtime
::
::  $pail: Vase with discrimator
|%
::  $tale: Data for a binding
+$  tale  (map slot pail)
::  $muck: Subtree in progress, i.e. no metadata yet
+$  muck  (axal tale)
::  $saga: complete binding
+$  saga  (pair aeon tale)
+$  lore  (pair slot vial)
::
+$  epic  $+(epic (axal saga))
+$  meal  (trap vase)
+$  suds
  $:  over=(set term)
  ==
+$  soap
  $:  over=(map term pith)
      loose=(unit term)
  ==
::  $soap: mode for $dish
:: $dish: map/filter overlay namespace
::  $?  %same  ::
+$  dish
  $:  in=(set norm)
      out=(set norm)
      fwd=$-(tale tale)
      back=(unit $-(tale tale))
  ==
+$  lens  [fwd=$-(tale tale) back=$-(tale tale)]
+$  norm  (pair slot stud)
+$  ewer  $-([pith epic] tale)
::
+$  tray
  $:  inputs=(set pith)
      run=$-((map term [pith tale]) tale)
  ==
--  =>
|%
+$  word
  $:  for=(set pith)
      =gift:dust
  :: case=@ud =mode]
  ==
+$  news  (axal word)
++  mode-from-note
  |=  n=note:dust
  ?-  -.n
    %poke  %dif
    %make  %add
    %cull  %del
  ==

++  dust
  ^?
  |%
  +$  gift
    $:  =care
        mod=(unit mode)
        =ever
        slots=(set slot)
    ==
  +$  toil  (axal note)
  +$  note
    $~  [%cull ~]
    $%  [%poke =tale]
        [%make =tale]
        [%cull ~]
    ==
  +$  sign  (axal gift)
  --
--  =>
|%
::  +vine: compute layer for namespace
++  vine
  ^?
  |%
  ::  $move: card with origin
  +$  move  (pair pith card)
  ::
  +$  gift  sign:dust
  +$  sign  sign:dust
  ::  $note: IO request at a location
  +$  note
    $~  [%cull ~]
    $%  [%poke =tale]
        [%make =tale]
        [%cull ~]
    ==
  ::
  +$  lard
    $~  [%cull ~ ~]
    $%  [%poke p=pith =tale]
        [%cull p=pith ~]
        [%make p=pith =tale]
    ==
  ::
  +$  card
    $~  [%cull ~ ~]
    $^  [p=card q=card]
    lard
  +$  bowl
    $:  our=@p
        here=pith
        now=@da
        eny=@uv
    ==
  +$  task
    $%  [%vine p=card:vine]
        [%hear =news]
    ==
  +$  fate
    $:  write=(list (pair pith note:dust))
        effects=(list move)
        todo=(unit task)
    ==

  --
+$  ovum  [src=pith =task:vine]        :: event for vine0
--  =>
|%
+$  wasp  *
+$  plea
  $%  [%meal id=@ =pith =gift:dust]
      [%page id=@ =pith =book]
      [%gone id=@ =pith]
      [%wack id=@ ~]
      [%ack id=@ ~]
      [%keen id=@ ~]
      [%step id=@ upon=@ud =time]
  ==
+$  writ
  $%  [%card id=@ =card:vine]
      [%peek id=@ case=(unit @ud) =hunt]
      [%keen id=@]
  ==
::
::  +drive: Path multiplexer core
::
--
~%  %sept-main  +  ~
|%
++  t  +
++  of  of:t
++  aon  aon:t
++  axal  axal:t
+$  case  @ud
++  drive
  |%
  ::  +en:drive: Multiplex several paths into one
  ::
  ::    See also: (+de:drive)
  ++  en
    =|  res=pith
    |=  ps=(list pith)
    ?~  ps
      res
    $(res (welp res [%ud (lent i.ps)] i.ps), ps t.ps)
  ++  one
    |=  pax=(pole iota)
    ^-  (unit [pith pith])
    ?>  ?=([[%ud count=@] rest=*] pax)
    ?.  (gte count.pax (lent rest.pax))
      ~
    `[(scag [count rest]:pax) (slag [count rest]:pax)]
  ::  +de:drive: Demultiplex one path into several
  ::
  ::    See also: (+en:drive)

  ++  de
    =|  res=(list pith)
    |=  pax=(pole iota)
    ^+  res
    ?:  =(~ pax)
      (flop res)
    =^  [ok=? nex=pith]  pax
      ?.  ?=([[%ud len=@] rest=*] pax)
        [[| ~] ~]
      ?.  (gte len.pax (lent rest.pax))
        [[| ~] ~]
      `[[? pith] (pole iota)]`[[& (scag [len rest]:pax)] (slag [len rest]:pax)]
    ?.  ok  ~
    $(res [nex res])
  ::  +pull:drive: pull one path from multiplexed
  ++  pull
    |=  pax=(pole iota)
    ^-  [pith (pole iota)]
    ?>  ?=([[%ud len=@] rest=*] pax)
    `[pith (pole iota)]`[(scag [len rest]:pax) (slag [len rest]:pax)]
  ++  push
    |=  [base=(pole iota) next=(pole iota)]
    ^-  pith
    (welp base (welp #/[ud/(lent next)] next))
  --
::
++  get-view
  |=  p=(pole iota)
  ^-  (unit view)
  ?.  ?=([[%ud case=@] rest=*] p)
    ~
  =/  fun-case=@ud     case.p
  =/  rest  rest.p
  =>  .(p `(pole iota)`p)
  =^  fun=pith  p
    (pull:drive rest)
  ?.  ?=([car=@tas rest=*] p)  ~
  ?~  car=((soft care) car.p)  ~
  `[[fun-case fun] [u.car rest.p]]
::
++  sorge
  |*  [=care:t epic=(axal:t)]
  ?-  care
    ?(%x %a)   epic(kid ~)
    ?(%y %b)   ~(snip of epic)
    ?(%z %c)   epic
  ==
::

++  u
  ~%  %u  ..u  ~
  |%
  ::
  ::  +get-stud-name: Get name for $stud
  ::
  ++  get-stud-name
    |=  =stud
    ?@  stud  stud
    (rear t.stud)
  ++  scod
    |=  i=iota
    ?@(i (scot %tas i) (scot i))
  ++  inc-mod
    |=  [x=@ud len=@ud]
    ?:  =(+(x) len)
      0
    +(x)
  ++  dec-mod
    |=  [x=@ud len=@ud]
    ?.  =(0 x)
      (dec x)
    (dec len)
  ::
  ++  is-parent
    ~/  %is-parent
    |=  [parent=pith:t kid=pith:t]
    ^-  ?
    ?~  parent  &
    ?~  kid     |
    ?.  =(i.parent i.kid)
      |
    $(parent t.parent, kid t.kid)
  --
::
++  uniq
  |*  a=(list)
  ^+  a
  ~(tap in (~(gas in *(set _?>(?=(^ a) i.a))) a))
++  pail-eq
  |=  [a=pail:t b=pail:t]
  =(a b)
::
++  diff-epic
  |=  [from=epic:t remove=epic:t]
  ^-  epic:t
  =?  fil.from  &(?=(^ fil.from) ?=(^ fil.remove) =(u.fil.from u.fil.remove))
    ~
  =/  kid  ~(tap aon kid.from)
  |-
  ?~  kid
    from
  %=  $
    kid.from  (~(put aon kid.from) -.i.kid ^$(from +.i.kid, remove (~(dip of remove) /[-.i.kid])))
    kid  t.kid
  ==

++  unm                                             ::  Urbit to Unix ms
  |=  a=@da
  =-  (div (mul - 1.000) ~s1)
  (sub (add a (div ~s1 2.000)) ~1970.1.1)

::
::  |eden: lifecycle and bootstrap formula generators
::
::    while unused by arvo itself, these nock formulas
::    bootstrap arvo and define its lifecycle.
::
::    we're creating an event series E whose lifecycle can be computed
::    with the urbit lifecycle formula L, `[2 [0 3] [0 2]]`.  that is:
::    if E is the list of events processed by a computer in its life,
::    its final state is S, where S is nock(E L).
::
::    in practice, the first five nouns in E are: two boot formulas,
::    a hoon compiler as a nock formula, the same compiler as source,
::    and the arvo kernel as source.
::
::    after the first five special events, we enter an iterative
::    sequence of regular events which continues for the rest of the
::    computer's life.  during this sequence, each state is a function
::    that, passed the next event, produces the next state.
::
::    a regular event is an $ovum, or `[date wire type data]` tuple, where
::    `date` is a 128-bit Urbit date; `wire` is an opaque path which
::    output can match to track causality; `type` is a symbol describing
::    the type of input; and `data` is input data specific to `type`.
::
::    in real life we don't actually run the lifecycle loop,
::    since real life is updated incrementally and also cares
::    about things like output.  we couple to the internal
::    structure of the state machine and work directly with
::    the underlying arvo engine.
::
::    this arvo core, which is at `+7` (Lisp `cddr`) of the state
::    function (see its public interface in `sys/arvo`), gives us
::    extra features, like output, which are relevant to running
::    a real-life urbit vm, but don't affect the formal definition.
::
::    so a real-life urbit interpreter is coupled to the shape of
::    the arvo core.  it becomes very hard to change this shape.
::    fortunately, it is not a very complex interface.
::
++  eden
  |%
  ::  +aeon: arvo lifecycle loop
  ::
  ::    the first event in a ship's log,
  ::    computing the final state from the rest of log
  ::    when invoked via the lifecycle formula: [%2 [%0 3] %0 2]
  ::
  ::    the formal urbit state is always just a gate (function)
  ::    which, passed the next event, produces the next state.
  ::
  ++  aeon
    ^-  *
    =>  ::  boot: kernel bootstrap, event 2
        ::  tale: events 3-n
        ::
        *log=[boot=* tale=*]
    !=  ::  arvo: bootstrapped kernel
        ::  epic: remainder of the log
        ::
    =+  [arvo epic]=.*(tale.log boot.log)
    |-  ^-  *
    ?@  epic  arvo
    %=  $
      epic  +.epic
      arvo  .*([arvo -.epic] [%9 2 %10 [6 %0 3] %0 2])
    ==
  ::
  ::  +boot: event 2: bootstrap a kernel from source
  ::
  ++  boot
    ^-  *
    ::
    ::  event 2 is the startup formula, which verifies the compiler
    ::  and starts the main lifecycle.
    ::
    =>  ::  fate: event 3: a nock formula producing the hoon bootstrap compiler
        ::  hoon: event 4: compiler source
        ::  arvo: event 5: kernel source
        ::  epic: event 6-n
        ::
        *log=[fate=* hoon=@ arvo=@ epic=*]
    !=
    ::
    ::  activate the compiler gate.  the product of this formula
    ::  is smaller than the formula.  so you might think we should
    ::  save the gate itself rather than the formula producing it.
    ::  but we have to run the formula at runtime, to register jets.
    ::
    ::  as always, we have to use raw nock as we have no type.
    ::  the gate is in fact ++ride.
    ::
    ~>  %slog.[0 leaf+"1-b"]
    =/  compiler-gate  .*(0 fate.log)
    ::
    ::  compile the compiler source, producing (pair span nock).
    ::  the compiler ignores its input so we use a trivial span.
    ::
    ~>  %slog.[0 leaf+"1-c (compiling compiler, wait a few minutes)"]
    =/  compiler-tool
      ~>  %bout
      .*([compiler-gate noun/hoon.log] [%9 2 %10 [6 %0 3] %0 2])
    ::
    ::  switch to the second-generation compiler.  we want to be
    ::  able to generate matching reflection nouns even if the
    ::  language changes -- the first-generation formula will
    ::  generate last-generation spans for `!>`, etc.
    ::
    ~>  %slog.[0 leaf+"1-d"]
    =.  compiler-gate  ~>(%bout .*(0 +.compiler-tool))
    ::
    ::  get the span (type) of the kernel core, which is the context
    ::  of the compiler gate.  we just compiled the compiler,
    ::  so we know the span (type) of the compiler gate.  its
    ::  context is at tree address `+>` (ie, `+7` or Lisp `cddr`).
    ::  we use the compiler again to infer this trivial program.
    ::
    ~>  %slog.[0 leaf+"1-e"]
    =/  kernel-span
      ~>  %bout
      -:.*([compiler-gate -.compiler-tool '+>'] [%9 2 %10 [6 %0 3] %0 2])
    ::
    ::  compile the arvo source against the kernel core.
    ::
    ~>  %slog.[0 leaf+"1-f"]
    =/  kernel-tool
      ~>  %bout
      .*([compiler-gate kernel-span arvo.log] [%9 2 %10 [6 %0 3] %0 2])
    ::
    ::  create the arvo kernel, whose subject is the kernel core.
    ::
    ~>  %slog.[0 leaf+"1-g"]
    ~>  %bout
    [.*(+>.compiler-gate +.kernel-tool) epic.log]
  --
::  +vere: helper core for runtime
::
::++  vere
  ::|%
  ::++  debuf
  ::  =>  |%
  ::      ++   grub  *
  ::      ++   fist  $-(done:pbuf grub)
  ::      --
  ::  |%
  ::  ++  slit
  ::    |=  =axis
  ::    |=  =done:pbuf
  ::    %+  skim  done
  ::    |=  =val:pbuf  =(q.q.val axis)
  ::  ++  tuple-raw
  ::    |*  wer=(pole [axis fist])
  ::    ?-    wer
  ::       [[key=@t *] t=*]
  ::      =>  .(wer [[* wit] *]=
  ::    =+
  ::
  ::  ++  map
  ::    |*  [keys=fist vals=fist]
  ::    |=  =done:pbuf
  ::    =|  out=(map (keys) (vals))
  ::    =|
  ::    ?~   done
  ::
  ::    %+  roll  done
  ::    |=  [=val:pbuf out=(map
  ::
  ::
  ::
  ::  ++  myth
  ::    |=  =myth:t
  ::    ^-  byts
  ::    %+  turn  ~(tap of myth)
  ::    |=  [=pith:t =vial:t]
  ::    ^-
  ::
  ::
  ::
  ::  |=  =byts
  ::  ^-

  ::++  pbuf
    ::~%  %pbuf  ..sept   ~
    ::|%
    ::+$  spec  ?(%var %chub %lent %word)
    ::+$  attr  (pair spec axis)
    ::+$  val   (pair byts attr)
    ::+$  done  (list val)
    ::+$  stag  @udstag
    ::+$  ktag  @udktag
    ::++  scribe
    ::  =<  scribe
    ::  |%
    ::  +$  scribe  (list @uxC)
    ::  ++  make
    ::    ::  ~%  %make-scribe  +>+   ~
    ::    |=  [len=@ byts=@]
    ::    ^-  scribe
    ::    ?>  (gte len (met 3 byts))
    ::    =+  (rip 3 byts)
    ::    (weld - (reap (sub len (met 3 byts)) 0x0))
    ::  ::
    ::  ++  read
    ::    |=  len=@ud
    ::    |=  s=scribe
    ::    =|  res=(list @)
    ::    |-  ^-  [@ _s]
    ::    ?:  =(len 0)  [(rap 3 (flop res)) s]
    ::    ?~  s  !!
    ::    $(res [i.s res], s t.s, len (dec len))
    ::  ++  read-chub  (read 8)
    ::  ++  read-word  (read 4)
    ::  ++  read-blob
    ::    |=  [len=@ud s=scribe]
    ::    ((read len) s)
    ::  --
    ::++  spec-to-tag
    ::  |=  =spec
    ::  ^-  stag
    ::  ?-  spec
    ::    %var   0
    ::    %chub  1
    ::    %lent  2
    ::    %word  5
    ::  ==
    ::++  spec-from-tag
    ::  |=  =stag
    ::  ^-  spec
    ::  ~|  stag/stag
    ::  ?+  stag  !!
    ::    %0    %var
    ::    %1    %chub
    ::    %2    %lent
    ::    %5    %word
    ::  ==
    ::++  list-for-axis
    ::  |=  [vals=(list val) =axis]
    ::  ^-  (list val)
    ::  %+  skim  vals
    ::  |=  =val
    ::  =(q.q.val axis)
    ::++  set-for-axis
    ::  |=  [vals=(list val) =axis]
    ::  ^-  (set val)
    ::  (~(gas in *(set val)) (list-for-axis vals axis))
    ::
    ::++  map-by-axis
    ::  |=  vals=(list val)
    ::  ^-  (map axis val)
    ::  %-  ~(gas by *(map axis val))
    ::  %+  turn  vals
    ::  |=  =val
    ::  [q.q.val val]
    ::::
    ::++  bite
    ::  |=  tom=@
    ::  ?:  =(tom 0)
    ::    [1 0]
    ::  [(met 3 tom) tom]
    ::++  barf
    ::  |%
    ::  ++  varint
    ::    =|  r=scribe
    ::    |=  var=@
    ::    ^-  scribe
    ::    ?:  (lth var 0x80)
    ::      (flop var r)
    ::    $(r [(mix 0x80 (dis 0x7f var)) r], var (rsh [0 7] var))
    ::  ::
    ::  ++  key
    ::    |=  =attr
    ::    ^-  scribe
    ::    =/  pec=@ud  (spec-to-tag p.attr)
    ::    =/  =axis  (lsh [0 3] q.attr)
    ::    (varint (mix axis pec))
    ::  ++  entry-force  %*(. entry force &)
    ::  ::
    ::  ++  entry
    ::    =|  force=_|
    ::    |=  =val
    ::    ::  ~&  entry/val
    ::    :: =-  ~&(entry-res/- -)
    ::    ^-  scribe
    ::    ?:  &(=(dat.p.val 0) !=(p.q.val %lent) !force)
    ::      ~
    ::      :: ~
    ::    %+  welp  (key q.val)
    ::    ?-  p.q.val
    ::        %var
    ::      (varint dat.p.val)
    ::        %chub
    ::      ?>  (lte (met 3 dat.p.val) 8)
    ::      (make:scribe 8 dat.p.val)
    ::        %word
    ::      ?>  (lte (met 3 dat.p.val) 4)
    ::      (make:scribe 4 dat.p.val)
    ::        %lent
    ::      (welp (varint wid.p.val) (make:scribe p.val))
    ::    ==
    ::  ++  entries
    ::    |=  =done
    ::    ^-  scribe
    ::    %-  zing
    ::    ^-  (list scribe)
    ::    %+  turn  done
    ::    |=  v=val
    ::    ^-  scribe
    ::    (entry v)
    ::  ++  step
    ::    |=  [upon=@ud =time]
    ::    %-  entries
    ::    :~  (var 1 upon)
    ::        (var 2 (unm time))
    ::    ==
    ::  ++  pee
    ::    |=  p=plea:t
    ::    ?+  -.p   ~|(-.p !!)
    ::          %step
    ::        ~&  p/p
    ::        %-  entries
    ::        :~  (var 1 id.p)
    ::            (knee 4 (step [upon time]:p))
    ::        ==
    ::
    ::          %page
    ::        %-  entries
    ::        :~  (var 1 id.p)
    ::            (knee 2 (page [pith book]:p))
    ::        ==
    ::      ::
    ::          %gone
    ::        %-  entries
    ::        :~  (var 1 id.p)
    ::            (pith 3 pith.p)
    ::        ==
    ::    ==
    ::  ++  var
    ::    |=  [=axis a=@ud]
    ::    ^-  val
    ::    [(bite a) var/axis]
    ::  ++  chub
    ::    |=  [=axis a=@ud]
    ::    ^-  val
    ::    [(bite a) chub/axis]
    ::  ++  lene
    ::    |=  [=axis =byts]
    ::    ^-  val
    ::    [byts lent/axis]
    ::  ++  knee
    ::    |=  [=axis s=scribe]
    ::    ^-  val
    ::    [[(lent s) (can 3 (turn s (lead 1)))] lent/axis]
    ::  ++  nown
    ::    |=  [=axis str=@]
    ::    ^-  val
    ::    (lene axis (bite str))
    ::  ++  string  nown
    ::  ++  pith
    ::    |=  [=axis pit=pith:t]
    ::    ^-  val
    ::    (string axis (en-cord:pith:t pit))
    ::  ::
    ::  ++  myth
    ::    |=  mit=myth:t
    ::    %-  entries
    ::    ^-  done
    ::    %+  turn  ~(tap by mit)
    ::    |=  [pit=pith:t vil=vial:t]
    ::    ^-  val
    ::    (knee 1 (twig pit vil))
    ::  ::
    ::  ++  twig
    ::    |=  [pit=pith:t val=vial:t]
    ::    %-  entries
    ::    :~  (pith 1 pit)
    ::        (knee 2 (vial val))
    ::    ==
    ::  ++  stud
    ::    |=  [=axis s=stud:t]
    ::    ?@  s  (nown axis s)
    ::    (pith axis s)
    ::  ++  scar-noun
    ::    |=  v=vial:t
    ::    %-  entries
    ::    :~  (stud 1 p.v)
    ::        (nown 2 'aaa')
    ::    ==
    ::  ++  scar-txt
    ::    |=  txt=@
    ::    %-  entries
    ::    :~  (string 2 txt)
    ::    ==
    ::  ++  scar-cube
    ::    |=  [s=stud:t cube=@t]
    ::    %-  entries
    ::    :~  (stud 1 s)
    ::        (string 2 cube)
    ::    ==
    ::  ++  scar-tang
    ::    |=  =tang
    ::    =;  txt=cord
    ::      %-  entries
    ::      :~  (string 2 txt)
    ::      ==
    ::    ~>  %memo./lain/json
    ::    %+  roll
    ::      ^-  wall
    ::      %-  zing
    ::      ^-  (list wall)
    ::      (turn tang |=(tan=tank (~(win re tan) [0 80])))
    ::
    ::    |=  [=tape out=cord]
    ::    ^+  out
    ::    :((cury cat 3) out '\0a' (crip tape))
    ::  ::
    ::
    ::  ::
    ::  ++  vial
    ::    |=  v=vial:t
    ::    %-  entry-force
    ::    ?+  p.v   (knee 5 (scar-noun v))
    ::       %txt  (knee 1 (scar-txt ;;(@ q.v)))
    ::       %hoon  (knee 2 (scar-txt ;;(@ q.v)))
    ::       %cant  (knee 6 (scar-cube p.v ;;(@t q.v)))
    ::       %pith  (knee 6 (scar-cube p.v (en-cord:pith:t ;;(pith:t q.v))))
    ::       %rpith  (knee 6 (scar-cube p.v (en-cord:pith:t ;;(pith:t q.v))))
    ::       %tang  (knee 5 (scar-tang ;;(tang q.v)))
    ::       %crew  (knee 3 (scar-mesh ;;(crew q.v)))
    ::       %duct  (knee 7 (scar-duct ;;((list pith:t) q.v)))
    ::       %atom  (knee 8 (make:scribe (bite ;;(@ q.v))))
    ::    ==
    ::  ++  scar-duct
    ::    |=  ps=(list pith:t)
    ::    %-  entries
    ::    %+  turn  ps
    ::    |=  p=pith:t
    ::    (pith 2 p)
    ::  ++  scar-mesh
    ::    |=  =crew:t
    ::    %-  entries
    ::    %+  turn  ~(tap by crew)
    ::    |=  [=term =pith:t]
    ::    (knee 2 (scar-mesh-entry term pith))
    ::  ++  scar-mesh-entry
    ::    |=  [=term p=pith:t]
    ::    %-  entries
    ::    :~  (string 1 term)
    ::        (pith 2 p)
    ::    ==
    ::  ++  oath
    ::    |=  oat=oath:t
    ::    (entries ~)
    ::  ++  ever
    ::    |=  ver=ever:t
    ::    %-  entries
    ::    :~  (var 1 p.exe.ver)
    ::        (var 2 q.exe.ver)
    ::        (var 3 p.why.ver)
    ::        (var 4 q.why.ver)
    ::        (var 5 p.zed.ver)
    ::        (var 6 q.zed.ver)
    ::        (var 6 q.zed.ver)
    ::        (var 7 (unm time.ver))
    ::    ==
    ::  ::
    ::  ++  aeon
    ::    |=  eon=aeon:t
    ::    %-  entries
    ::    :~  (knee 1 (ever p.eon))
    ::        (knee 2 (oath q.eon))
    ::    ==
    ::  ::
    ::  ++  book
    ::    |=  [eon=aeon:t mit=myth:t]
    ::    %-  entries
    ::    :~  (knee 1 (aeon eon))
    ::        (knee 2 (myth mit))
    ::    ==
    ::  ++  page
    ::    |=  [pit=pith:t b=book:t]
    ::    %-  entries
    ::    :~  (pith 1 pit)
    ::        (knee 2 (book b))
    ::    ==
    ::  --
    ::::
    ::++  feed
    ::  |%
    ::
    ::  ++  writ
    ::    |=  =byts
    ::    ^-  ^writ
    ::    =/  ents=(list val)
    ::      (entries (make:scribe byts))
    ::
    ::    =/  meep  (map-by-axis ents)
    ::    =/  id  dat.p:(~(got by meep) 1)
    ::    ?^  cad=(~(get by meep) 2)
    ::      [%card id (card p.u.cad)]
    ::    [%peek id (peek p:(~(got by meep) 3))]
    ::  ++  peek
    ::    |=  =byts
    ::    ^-  [~ hunt:t]
    ::    !!
    ::  ::
    ::  ++  pith
    ::    |=  =val
    ::    ^-  pith:t
    ::    ~|  ;;(@t dat.p.val)
    ::    (pave (stab dat.p.val))
    ::  ++  card
    ::    |=  =byts
    ::    ^-  card:vine
    ::    =/  ents=(list val)
    ::      (entries (make:scribe byts))
    ::    =/  meep  (map-by-axis ents)
    ::    ~|  entries/meep
    ::    :-  (pith (~(got by meep) 1))
    ::    (note p:(~(got by meep) 2))
    ::  ++  note
    ::    |=  =byts
    ::    ^-  note:vine
    ::    =/  ents=(list val)
    ::      (entries (make:scribe byts))
    ::    =/  meep  (map-by-axis ents)
    ::    ~|  meep/meep
    ::    =/  mote=@  dat.p:(~(gut by meep) 1 `val`[[0 0] %var 1])
    ::    ~|  mote/mote
    ::    ?+  mote  !!
    ::       %0  make/(myth p:(~(got by meep) 2))
    ::       %1  poke/(myth p:(~(got by meep) 2))
    ::       %2  cull/~
    ::     ==
    ::  ++  myth
    ::    |=  =byts
    ::    ^-  myth:t
    ::    =/  ents=(list val)
    ::      (entries (make:scribe byts))
    ::    %-  ~(gas by *(map pith:t vial:t))
    ::    %+  turn  (list-for-axis ents 1)
    ::    |=  =val
    ::    (myth-entry p.val)
    ::  ++  myth-entry
    ::    |=  =byts
    ::    ^-  [pith:t vial:t]
    ::    =/  ents=(list val)
    ::      (entries (make:scribe byts))
    ::    =/  meep  (map-by-axis ents)
    ::    [(pith (~(got by meep) 1)) (vial p:(~(got by meep) 2))]
    ::  ::
    ::  ++  vial
    ::    |=  =byts
    ::    ^-  vial:t
    ::    =/  ents=(list val)
    ::      (entries (make:scribe byts))
    ::    =/  meep  (map-by-axis ents)
    ::    ~|  meep/~(key by meep)
    ::    ?^  txt=(~(get by meep) 1)
    ::      (scar-text p.u.txt)
    ::    ?^  duc=(~(get by meep) 7)
    ::      (scar-duct p.u.duc)
    ::    ?^  mes=(~(get by meep) 3)
    ::      (scar-mesh p.u.mes)
    ::    ?^  tom=(~(get by meep) 8)
    ::      [/stddat.p.u.tom
    ::      :: (scar-atom p.u.doc)
    ::    (scar-cube p:(~(got by meep) 6))
    ::  ++  scar-mesh
    ::    |=  =byts
    ::    =/  ents=(list val)
    ::      (entries (make:scribe byts))
    ::    :-  %crew
    ::    %-  ~(gas by *crew:t)
    ::    %+  turn  (list-for-axis ents 2)
    ::    |=  =val
    ::    (scar-mesh-entry p.val)
    ::  ++  scar-mesh-entry
    ::    |=  =byts
    ::    =/  ents=(list val)
    ::      (entries (make:scribe byts))
    ::    =/  meep  (map-by-axis ents)
    ::    =/  str
    ::      ?~  str=(~(get by meep) 1)
    ::        ''
    ::      ;;(@t dat.p.u.str)
    ::    =/  =pith:t
    ::      ?~  pit=(~(get by meep) 2)
    ::        *pith:t
    ::      (pith u.pit)
    ::    [str pith]
    ::  ::
    ::  ++  scar-duct
    ::    |=  =byts
    ::    ^-  vial:t
    ::    =/  ents=(list val)
    ::      (entries (make:scribe byts))
    ::    :-  /std/pro/duct
    ::    %+  turn  (list-for-axis ents 2)
    ::    |=  =val
    ::    (pith val)
    ::  ::
    ::  ++  scar-cube
    ::    |=  =byts
    ::    ^-  vial:t
    ::    =/  ents=(list val)
    ::      (entries (make:scribe byts))
    ::    =/  meep  (map-by-axis ents)
    ::    =+  ;;(typ=@t dat.p:(~(got by meep) 1))
    ::    =/  dat  dat.p:(~(got by meep) 2)
    ::    ?+  typ  !!
    ::      %cant  cant/dat
    ::    ==
    ::  ++  scar-text
    ::    |=  =byts
    ::    =/  ents=(list val)
    ::      (entries (make:scribe byts))
    ::    =/  meep  (map-by-axis ents)
    ::    ~|  meep
    ::    ?~  txt=(~(get by meep) 2)
    ::      [%txt '']
    ::    [%txt dat.p.u.txt]
    ::
    ::  ::
    ::  ::
    ::  ++  varint
    ::    =|  res=@ud
    ::    =|  size=@ud
    ::    |=  =scribe
    ::    ^-  [byts _scribe]
    ::    ?~  scribe  !!
    ::    =/  nex  (dis i.scribe 0x7f)
    ::    =.  res  (mix res (lsh [0 (mul size 7)] nex))
    ::    ?.  =(1 (rsh [0 7] i.scribe))
    ::      [[+(size) res] t.scribe]
    ::    $(size +(size), scribe t.scribe)
    ::  ++  key
    ::    |=  =scribe
    ::    ~|  scribe/scribe
    ::    ^-  [attr _scribe]
    ::    =^  =byts  scribe  (varint scribe)
    ::    =/  =spec  (spec-from-tag (dis 0b111 dat.byts))
    ::    =/  =axis  (rsh [0 3] dat.byts)
    ::    [[spec axis] scribe]
    ::  ++  entries
    ::    =|  res=(list val)
    ::    |=  s=scribe
    ::    ?:  =(~ s)  (flop res)
    ::    =^  =val:pbuf:vere  s  (entry:feed:pbuf:vere s)
    ::    $(res [val res])
    ::  ++  entry
    ::    |=  s=scribe
    ::    ^-  [val _s]
    ::    =^  =attr  s  (key s)
    ::    ?-  p.attr
    ::        %var
    ::      =^  =byts  s  (varint s)
    ::      [[byts attr] s]
    ::        %chub
    ::      =^  chub=@   s  (read-chub:scribe s)
    ::      [[[8 chub] attr] s]
    ::        %word
    ::      =^  word=@   s  (read-word:scribe s)
    ::      [[[4 word] attr] s]
    ::        %lent
    ::      =^  len=byts  s  (varint s)
    ::      =^  blob=@  s  (read-blob:scribe dat.len s)
    ::      [[[dat.len blob] attr] s]
    ::    ==
    ::  --
    ::--
    ::
  ::
  ::++  feed
  ::  |%
  ::  ++  page
  ::    |=  [id=@ pax=pith:t mit=myth:t]
  ::    ~|  pax/pax
  ::    ^-  byts  %-  bite
  ::    %+  can  3
  ::    :~  (u32 id)
  ::        (pith pax)
  ::        (myth mit)
  ::    ==
  ::  ++  axes
  ::    |=  [ax=@ atom=@]
  ::    %-  bite
  ::    %+  can  3
  ::    :~  (u32 ax)
  ::        (blob atom)
  ::    ==
  ::  ++  noun
  ::    |=  non=*
  ::    %-  blob
  ::    =;  byt=(unit @)
  ::      ?~  byt  (can 3 ~[(axes 1 %wack)])
  ::      u.byt
  ::    %-  mole  |.
  ::    %+  can  3
  ::    =/  ax  1
  ::    |-  ^-  (list byts)
  ::    ?@  non  ~[(axes ax non)]
  ::    %+  welp  $(non -.non, ax (mul 2 ax))
  ::    $(non +.non, ax +((mul 2 ax)))
  ::  ++  poem
  ::    |=  p=poem:t
  ::    %-  bite
  ::    %+  can  3
  ::    :~  (stud code.p)
  ::        (u32 -.bolt.p)
  ::    ==
  ::  ++  vial
  ::    |=  v=vial:t
  ::    ^-  byts
  ::    %-  bite
  ::    %+  can  3
  ::    :~  (stud p.v)
  ::        ?+  p.v  (noun q.v)
  ::            %vase  (noun 'vase')
  ::            %tang
  ::          (noun 'tang')
  ::        ==
  ::    ==
  ::  ::
  ::  ++  myth
  ::    |=  mit=myth:t
  ::    ^-  byts
  ::    %-  blob
  ::    %+  can  3
  ::    %-  zing
  ::    %+  turn  ~(tap by mit)
  ::    |=  [slot=pith:t v=vial:t]
  ::    :~  (pith slot)
  ::        (vial v)
  ::    ==
  ::  ::
  ::  ++  stud
  ::    |=  =stud:t
  ::    ^-  byts
  ::    ~|  stud/stud
  ::    ?>  ?=(@ stud)
  ::    (cord stud)
  ::  ++  u32
  ::    |=  a=@
  ::    ^-  byts
  ::    ?>  (lte a (dec (bex 32)))
  ::    [4 a]
  ::
  ::  ++  u64
  ::    |=  a=@
  ::    ^-  byts
  ::    ?>  (lte a (dec (bex 64)))
  ::    [8 a]
  ::  ++  weld
  ::    |=  [a=byts b=byts]
  ::    [(add wid.a wid.b) (cat 3 dat.a dat.b)]
  ::  ::
  ::  ++  bite
  ::    |=  tom=@
  ::    ?:  =(tom 0)
  ::      [0 0]
  ::    [(met 3 tom) tom]
  ::  ++  cord  blob
  ::  ++  blob
  ::    |=  blob=@
  ::    ^-  byts  %-  bite
  ::    =/  siz
  ::      ?:  =(blob 0)  1
  ::      (met 3 blob)
  ::    =?  blob  (gte siz 4.096)
  ::      '<too big>'
  ::    (can 3 (u64 (met 3 blob)) (bite blob) ~)
  ::  ::
  ::  ++  pith
  ::    |=  =pith:t
  ::    ^-  byts
  ::    (cord (spat (pout pith)))
  ::  ++  mode
  ::    |=  =mode:t
  ::    ^-  byts
  ::    :-  1
  ::    ?-  mode
  ::      %add  'c'
  ::      %dif  'u'
  ::      %del  'd'
  ::    ==
  ::  ++  lock
  ::    |=  =lock:t
  ::    :-  16
  ::    %+  can  3
  ::    :~  (u64 p.lock)
  ::        (u64 q.lock)
  ::    ==
  ::  ++  ever
  ::    |=  =ever:t
  ::    :-  64
  ::    %+  can  3
  ::    :~  (lock exe.ever)
  ::        (lock why.ever)
  ::        (lock zed.ever)
  ::        [16 time.ever]
  ::    ==
  ::  ::
  ::  ++  gift
  ::    |=  =gift:dust:t
  ::    ^-  byts
  ::    %-  bite
  ::    %+  can  3
  ::    :~  (ever ever.gift)
  ::        ?~(mod.gift 1^0 (mode u.mod.gift))
  ::        [1 care.gift]
  ::
  ::    ==
  ::  ++  plea
  ::    |=  p=plea:t
  ::    ^-  byts
  ::    %+  weld  [4 -.p]
  ::    ?+  -.p  !!
  ::      %keen  [0 0]
  ::      %meal  (meal +>.p)
  ::      :: %page  (page +.p)
  ::    ==
  ::
  ::  ::
  ::  ++  meal
  ::    |=  [p=pith:t gif=gift:dust:t]
  ::    ^-  byts
  ::    %-  bite
  ::    %+  can  3
  ::    :~  (pith p)
  ::        (gift gif)
  ::    ==
  ::  -- :: feed
  ::++  barf
  ::  =>  |%
  ::      +$  scribe  (list @uxC)
  ::      ++  make-scribe
  ::        |=  [len=@ byts=@]
  ::        =+  (rip 3 byts)
  ::        (weld - (reap (sub len (met 3 byts)) 0x0))
  ::
  ::      ++  read-len
  ::        |=  len=@ud
  ::        |=  s=scribe
  ::        =|  res=(list @)
  ::        |-  ^-  [@ _s]
  ::        ?:  =(len 0)  [(rap 3 (flop res)) s]
  ::        ?~  s  !!
  ::        $(res [i.s res], s t.s, len (dec len))
  ::      --
  ::  |%
  ::  ++  chub  (read-len 8)
  ::  ++  word  (read-len 4)
  ::  ++  char  (read-len 1)
  ::  ++  read-str
  ::    |=  s=scribe
  ::    =^  len=@    s  (word s)
  ::    ~&  len/len
  ::    =^  str=@t   s  ((read-len len) s)
  ::    ~&  read-str/str
  ::    [str s]
  ::  ++  read-pith
  ::    |=  s=scribe
  ::    ^-  [pith:t _s]
  ::    =^  str=@t  s  (read-str s)
  ::    ~|  pith/str
  ::    [(pave (stab str)) s]
  ::  ++  read-axis
  ::    |=  s=scribe
  ::    ^-  [[@ @] _s]
  ::    =^  ax=@t  s   (word s)
  ::    =^  tom=@  s   (read-str s)
  ::    [[ax tom] s]
  ::  ::
  ::  ++  read-noun
  ::    |=  s=scribe
  ::    =^  len=@   s  (word s)
  ::    =|  axes=(map @ @)
  ::    |-  ^-  [* _s]
  ::    ?:  =(len 0)  [(adze axes) s]
  ::    =^  [ax=@ tom=@]   s  (read-axis s)
  ::    $(axes (~(put by axes) ax tom), len (dec len))
  ::  ++  read-myth
  ::    |=  s=scribe
  ::    ^-  [myth:t _s]
  ::    [*myth:t s]
  ::
  ::    ::=^  len=@   s  (word s)
  ::    ::=|  =myth:t
  ::    ::|-  ^+  [myth s]
  ::    ::?:  =(0 len)  [myth ret-s]
  ::    ::=^  =pith:t  s  (read-pith s)
  ::    ::=^  =vial:t  s  (read-vial s)
  ::    ::$(myth (~(put by myth) pith vial), len (dec len))
  ::  ::
  ::  ++  read-vial
  ::    |=  s=scribe
  ::    =^  =stud:t  s  (read-str s)
  ::    =^  non=*    s  (read-noun s)
  ::    [[stud non] s]
  ::  ::
  ::  ++  writ
  ::    |=  [len=@ byts=@]
  ::    ^-  ^writ
  ::    =/  s  (make-scribe +<)
  ::    =^  mote=@tas  s  (word s)
  ::    ?+  mote  ~|(weird-write/mote !!)
  ::      %peek  (peek s)
  ::      %task  !!
  ::      %keen  [%keen ~]
  ::    ==
  ::  ++  peek
  ::    |=  s=scribe
  ::    =^  id=@ud    s   (word s)
  ::    =^  case=@ud  s   (word s)
  ::    =^  car=@t   s   (char s)
  ::    =+  ;;(=care:t car)
  ::    =^  =pith:t  s  (read-pith s)
  ::    [%peek id ?:(=(id 0) ~ `id) care pith]
  ::  ++  task
  ::    |=  s=scribe
  ::    :-  %task
  ::    =^  id=@ud     s   (word s)
  ::    :-  id
  ::    =^  mote=@tas  s  (word s)
  ::    :-  %vine  ?>  ?=(%vine mote)
  ::    =^  =pith:t    s  (read-pith s)
  ::    :-  pith
  ::    =^  mote=@tas  s  (word s)
  ::    ?+  mote  ~|(weird-card/mote !!)
  ::        %cull    cull/~
  ::    ::
  ::        %poke
  ::      =^  =myth:t  s  (read-myth s)
  ::      poke/myth
  ::    ::
  ::        %make
  ::      =^  =myth:t  s  (read-myth s)
  ::      make/myth
  ::    ==
  ::  ::
  ::  ++  adze
  ::    =+  ax=1
  ::    |=  a=(map @ @)
  ::    ^-  *
  ::    ?^  non=(~(get by a) ax)  u.non
  ::    [$(ax (peg ax 2)) $(ax (peg ax 3))]
  ::  --
  ::++  gas-of
  ::  |*  [a=(axal) ls=(list)]
  ::  (~(gas of a) ls)
  :::: xx: stupid, how to door inside vere?
  ::++  tap-of
  ::  |*  a=(axal)
  ::  ~(tap of a)
  ::  +paper: effect manipulation
  ::++  paper
  ::  |=  =sign:dust:t
  ::  ^-  clue:dust:t

  ::-- :: vere
--
