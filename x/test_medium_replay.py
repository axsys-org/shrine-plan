import unittest
from replay_medium_local import complete_history


class ReplayBoundary(unittest.TestCase):
    def frame(self, kinds=('define', 'description')):
        events = [dict(id=str(i), basis=str(i), kind=k, body='{}')
                  for i, k in enumerate(kinds, 1)]
        return dict(expected=str(len(events)+1), events=list(reversed(events)) +
                    [dict(id='', basis='0', kind='', body='')])

    def test_complete_history_and_native_padding(self):
        self.assertEqual([e['id'] for e in complete_history(self.frame())], ['1', '2'])

    def test_truncation_is_not_treated_as_export(self):
        frame = self.frame()
        frame['events'].pop(1)
        with self.assertRaises(ValueError): complete_history(frame)

    def test_actions_are_not_replayed_as_effects(self):
        with self.assertRaises(ValueError): complete_history(self.frame(('define', 'act')))

    def test_pure_actions_require_explicit_boundary_and_opt_in(self):
        frame=self.frame(('define','act'))
        with self.assertRaises(ValueError): complete_history(frame,True)
        frame['features']=['native-definition-actions']
        with self.assertRaises(ValueError): complete_history(frame)
        self.assertEqual(len(complete_history(frame,True)),2)

    def test_binding_reconstruction_keeps_complete_history_requirement(self):
        frame=self.frame(('author','instantiate','detach','rebind'))
        self.assertEqual(len(complete_history(frame)),4)
        frame['events'].pop(1)
        with self.assertRaises(ValueError): complete_history(frame)

    def test_repeated_identity_rejected(self):
        frame = self.frame()
        frame['events'][0]['id'] = frame['events'][1]['id']
        with self.assertRaises(ValueError): complete_history(frame)


if __name__ == '__main__': unittest.main()
