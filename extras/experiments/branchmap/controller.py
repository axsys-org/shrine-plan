"""Branchmap semantic controller. SHA-256 demo IDs; no chain or token enforcement."""
import hashlib,json
TOP='0'*64

def digest(domain,value):
    return hashlib.sha256((domain+'\0'+json.dumps(value,sort_keys=True,separators=(',',':'))).encode()).hexdigest()

def canonical(assignments):
    result={}
    for predicate,outcome in assignments:
        if predicate in result and result[predicate]!=outcome:
            raise ValueError('contradictory outcomes for predicate '+predicate)
        result[predicate]=outcome
    return tuple(sorted(result.items()))

def verse(assignments):
    items=canonical(assignments)
    return TOP if not items else digest('BRANCHMAP_SHRINE_DEMO_VERSE_V1',items)

def asset(root,assignments):
    return digest('BRANCHMAP_SHRINE_DEMO_ASSET_V1',[root,verse(assignments)])

def split(root,assignments,predicate,outcomes,quantity):
    items=canonical(assignments)
    if predicate in dict(items): raise ValueError('predicate already assigned')
    if quantity<=0 or len(outcomes)<2 or len(set(outcomes))!=len(outcomes): raise ValueError('invalid split family')
    return [{'root':root,'assignments':canonical([*items,(predicate,o)]),'quantity':quantity} for o in outcomes]

def merge(children,parent,predicate,outcomes):
    parent=canonical(parent)
    if not children: raise ValueError('empty family')
    root=children[0]['root']; quantity=children[0]['quantity']
    expected={canonical([*parent,(predicate,o)]) for o in outcomes}
    actual=[canonical(c['assignments']) for c in children]
    if len(actual)!=len(expected) or set(actual)!=expected: raise ValueError('complete sibling family required')
    if any(c['root']!=root or c['quantity']!=quantity for c in children): raise ValueError('root and quantities must match')
    return {'root':root,'assignments':parent,'quantity':quantity}

def normalize(assignments,resolved):
    remaining=[]
    for p,o in canonical(assignments):
        if p not in resolved: remaining.append((p,o))
        elif resolved[p]!=o: return {'status':'invalid','verse':None,'assignments':[]}
    return {'status':'valid','verse':verse(remaining),'assignments':remaining}

def checks(a='a',b='b'):
    ab=[(a,'yes'),(b,'no')]
    family=split('demo-usdc',[],a,['yes','no'],100)
    results={
      'order_independent':verse(ab)==verse(list(reversed(ab))),
      'duplicate_idempotent':verse(ab)==verse(ab+[(a,'yes')]),
      'top_reserved':verse([])==TOP,
      'split_each_branch_quantity':all(c['quantity']==100 for c in family),
      'merge_restores_quantity':merge(family,[],a,['yes','no'])['quantity']==100,
      'matching_resolution_removes_assignment':normalize(ab,{a:'yes'})['assignments']==[(b,'no')],
      'contradictory_resolution_invalidates':normalize(ab,{a:'no'})['status']=='invalid',
      'all_resolved_is_top':normalize(ab,{a:'yes',b:'no'})['verse']==TOP,
      'asset_order_independent':asset('demo-usdc',ab)==asset('demo-usdc',list(reversed(ab))),
      'asset_roots_distinct':asset('demo-usdc',ab)!=asset('demo-btc',ab),
      'four_outcome_split_complete':len(split('demo-usdc',[],a,['one','two','three','four'],100))==4,
      'four_outcome_merge_restores':merge(split('demo-usdc',[],a,['one','two','three','four'],100),[],a,['one','two','three','four'])['quantity']==100,
    }
    for name,fn in [('contradiction_rejected',lambda:canonical([(a,'yes'),(a,'no')])),('missing_sibling_rejected',lambda:merge(family[:1],[],a,['yes','no'])),('unequal_quantity_merge_rejected',lambda:merge([family[0],dict(family[1],quantity=99)],[],a,['yes','no'])),('different_root_merge_rejected',lambda:merge([family[0],dict(family[1],root='demo-btc')],[],a,['yes','no'])),('duplicate_sibling_merge_rejected',lambda:merge([family[0],family[0]],[],a,['yes','no'])),('repeat_predicate_split_rejected',lambda:split('demo-usdc',[(a,'yes')],a,['yes','no'],100))]:
        try: fn();results[name]=False
        except ValueError: results[name]=True
    assert all(results.values()),results
    return results

if __name__=='__main__': print(json.dumps(checks(),indent=2))
