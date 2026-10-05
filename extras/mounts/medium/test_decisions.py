"""Finite-choice boundaries: names never change executable actions."""
import unittest
from decisions import catalog

class DecisionsTest(unittest.TestCase):
    def setUp(self):
        self.collection={'id':'/source','parent':'/','label':'One name','properties':[{'label':'phase','slot':'/phase'}]}
        self.material={'nodes':[self.collection,{'id':'/record','parent':'/source','properties':[{'label':'phase','value':'Ready'}]}]}
        self.scene={'blocks':[{'id':'shape','part':'shape'}]}
    def test_names_do_not_dispatch(self):
        before=catalog(self.scene,self.material)
        self.collection['label']='A completely unfamiliar domain'
        after=catalog(self.scene,self.material)
        self.assertEqual([x['action'] for x in before],[x['action'] for x in after])
        self.assertEqual([x['id'] for x in before],[x['id'] for x in after])
    def test_exact_field_identity(self):
        scope={'target':'shape','field':{'collection':'/source','slot':'/phase'}}
        options=catalog(self.scene,self.material,scope=scope)
        shares=[o for o in options if o['action']['op']=='shape_share']
        self.assertEqual(shares[0]['action']['equals'],'Ready')
        scope['field']['slot']='/invented'
        self.assertFalse(any(o['action']['op']=='shape_share' for o in catalog(self.scene,self.material,scope=scope)))
    def test_mapping_choices_cannot_invent_fields_or_numeric_encodings(self):
        scope={'target':'shape','field':{'collection':'/source','slot':'/phase'}}
        encodings=[o['action'] for o in catalog(self.scene,self.material,scope=scope) if o['action']['op']=='encoding']
        self.assertEqual({a['channel'] for a in encodings},{'label','colour','row'})
        self.assertTrue(all(a['slot']=='/phase' for a in encodings))
        self.material['nodes'][1]['properties'][0]['value']='12'
        encodings=[o['action'] for o in catalog(self.scene,self.material,scope=scope) if o['action']['op']=='encoding']
        self.assertIn('angle',{a['channel'] for a in encodings})

    def test_share_choices_survive_empty_data(self):
        self.collection['properties'][0].update(type='Enum', choices=['Queued','Ready'])
        self.material['nodes']=self.material['nodes'][:1]
        options=catalog(self.scene,self.material,scope={'target':'shape','field':{'collection':'/source','slot':'/phase'}})
        self.assertEqual([o['action']['equals'] for o in options if o['action']['op']=='shape_share'],['Queued','Ready'])

    def test_empty_collection_is_still_presentable(self):
        self.material['nodes']=self.material['nodes'][:1]
        options=catalog(self.scene,self.material,scope={'collection':'/source'})
        self.assertTrue(any(o['action'].get('part')=='table' for o in options))
        self.assertFalse(any(o['action']['op']=='place' for o in options))
        self.assertEqual(options[-1]['action']['op'],'question')

if __name__=='__main__': unittest.main()
