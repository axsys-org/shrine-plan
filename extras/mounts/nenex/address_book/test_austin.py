import unittest
from austin import normalize, overlay


class AddressImportTests(unittest.TestCase):
    def row(self, **changes):
        return dict(PLACE_ID=91412, ADDRESS=301, ADDRESS_FRACTION=None,
                    PREFIX_DIRECTION='W', STREET_NAME='2ND', STREET_TYPE='ST',
                    SUFFIX_DIRECTION=' ', FULL_STREET_NAME='301 W 2ND ST',
                    ADDRESS_TYPE=1, PARENT_PLACE_ID=23, SEGMENT_ID=45, OBJECTID=67,
                    **changes)

    def test_fraction_is_text(self):
        row=self.row();row['ADDRESS_FRACTION']='1/2'
        page, street, label, packed=normalize(row)
        self.assertEqual(page,91)
        self.assertEqual(packed.split('|')[1],'301 1/2')
        self.assertEqual(len(packed.split('|')),9)

    def test_street_designation_includes_directions(self):
        row=self.row();other=dict(row,PREFIX_DIRECTION='E')
        self.assertNotEqual(normalize(row)[1],normalize(other)[1])
        self.assertEqual(normalize(row)[1],normalize(dict(row,ADDRESS=999))[1])

    def test_absence_does_not_become_none_text(self):
        row=self.row();row['PARENT_PLACE_ID']=None
        self.assertEqual(normalize(row)[3].split('|')[6],'')

    def test_reserved_delimiters_refuse(self):
        row=self.row();row['STREET_NAME']='INVALID|FIELD'
        with self.assertRaises(AssertionError):normalize(row)

    def test_source_is_not_mutated(self):
        row=self.row();before=dict(row);normalize(row)
        self.assertEqual(row,before)

    def test_overlay_lengths_include_data_page(self):
        self.assertEqual(overlay('/a/b',3,'/c/d/e'),'/o/3/2/a/b/3/c/d/e')


if __name__=='__main__':unittest.main()
