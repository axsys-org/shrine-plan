"""Address/CRM projections built from the existing native Foil cell library.

No evaluator, polling worker, geometry store, or alternate object model.
All entity edges are path pails; dependency bindings are safe references.
"""
S = '/0x11/gov/nenex_ui/'


def path(value):
    return {'type': 'path', 'value': value}


def reference(value, care='y'):
    return {'type': 'reference', 'path': value, 'care': care, 'case': 0}


def slot(name):
    return S + name


def projections(root, contacts, directory, associations, formulas, *, address_table=None):
    """Return reusable cell bindings. Collections must carry /sys/about paths.

    Applying this recipe to another set of collections changes only its inputs.
    Optional/missing joins preserve the row without inventing an address.
    """
    records = []

    def cell(name, formula, source, **settings):
        target = root + '/' + name
        records.append({'path': target, 'slots': {
            '/sys/lede': name.replace('_', ' '),
            '/sys/weft': formulas[formula], '/sys/tack': reference(source),
            **settings}})
        return '/x' + target

    def lookup(name, source, key, table, take, into):
        return cell(name, 'lookup', source, key=slot(key), match='/sys/about',
                    table=reference(table), take=take, into=slot(into))

    if address_table is not None:
        addresses = address_table
    else:
        addresses = directory + '/addresses'
        for field, table in [('street', 'streets'), ('locality', 'localities'),
                             ('region', 'regions'), ('country', 'countries')]:
            addresses = lookup('address_' + field, addresses, 'address_' + field,
                               directory + '/' + table, '/sys/lede', 'address_' + field + '_label')
        addresses = cell('address_line', 'join', addresses,
                         slots=' '.join(slot(x) for x in ('address_number', 'address_street_label', 'address_unit')),
                         into=slot('address_line'), **{'with': ' '})
        addresses = cell('address_city_line', 'join', addresses,
                         slots=' '.join(slot(x) for x in ('address_locality_label', 'address_region_label', 'address_postal_code')),
                         into=slot('address_city_line'), **{'with': ' '})
        addresses = cell('addresses', 'join', addresses,
                         slots=' '.join(slot(x) for x in ('address_line', 'address_city_line', 'address_country_label')),
                         into=slot('address_label'), **{'with': ', '})
    contacts = lookup('contact_names', contacts, 'contact_person', directory + '/people', '/sys/lede', 'contact_name')
    contacts = lookup('contact_addresses', contacts, 'contact_workplace', associations,
                      slot('association_address'), 'contact_address_target')
    contacts = lookup('contact_purposes', contacts, 'contact_workplace', associations,
                      slot('association_purpose'), 'contact_address_purpose')
    contacts = lookup('contact_verification', contacts, 'contact_workplace', associations,
                      slot('association_verification'), 'contact_address_verification')
    contacts = lookup('contacts', contacts, 'contact_address_target', addresses,
                      slot('address_label'), 'contact_address_label')
    return records, {'addresses': addresses, 'contacts': contacts}


def seed(directory, crm, contacts, evidence):
    """Synthetic demonstration only: three shared offices, nine associations.

    Existing contacts are poked with additional facets, never replaced.
    No postal validity, occupancy, residence or deliverability is asserted.
    """
    records = []

    def add(target, values, action='make'):
        records.append({'path': target, 'action': action, 'slots': values})

    def entity(target, label, **values):
        add(target, {'/sys/about': path(target), '/sys/lede': label, **values})

    entity(directory, 'Shared directory')
    for name in ('people', 'addresses', 'streets', 'localities', 'regions', 'countries'):
        entity(directory + '/' + name, name)
    entity(directory + '/localities/austin', 'Austin')
    entity(directory + '/regions/texas', 'TX')
    entity(directory + '/countries/us', 'US')
    entity(evidence, 'Fictional address association evidence', is_synthetic=True,
           source='generated_demo', description='Fabricated office addresses for a CRM demonstration; no occupancy or deliverability claim.')
    for value in ('workplace', 'demo_unverified'):
        entity(directory + '/vocabulary/' + value, value.replace('_', ' '))
    associations = crm + '/address_links'
    entity(associations, 'Contact-address associations (fictional)')
    for i, street in enumerate(('Example Alder Lane', 'Example Harbor Avenue', 'Example Copper Street'), 1):
        street_path = directory + '/streets/demo_' + str(i)
        entity(street_path, street, is_synthetic=True)
        source = evidence + '/office_' + str(i)
        raw = {'number': str(i * 100), 'street': street, 'unit': 'Suite 100',
               'city': 'Austin', 'region': 'TX', 'postal_code': '78701', 'country': 'US'}
        entity(source, 'Generated office ' + str(i), is_synthetic=True, **raw)
        values = {slot('address_number'): raw['number'], slot('address_unit'): raw['unit'],
                  slot('address_street'): path(street_path),
                  slot('address_locality'): path(directory + '/localities/austin'),
                  slot('address_region'): path(directory + '/regions/texas'),
                  slot('address_country'): path(directory + '/countries/us'),
                  slot('address_postal_code'): raw['postal_code'],
                  slot('address_source'): path(source), 'is_synthetic': True}
        entity(directory + '/addresses/demo_office_' + str(i), 'Demo office ' + str(i), **values)
    for i, contact in enumerate(sorted(contacts, key=lambda x: x['path'])):
        old = contact['properties']
        target = contact['path']
        ident = target.rsplit('/', 1)[1]
        person = directory + '/people/' + ident
        entity(person, old.get('/name', old.get('/sys/lede', ident)), is_synthetic=True)
        values = {slot('contact_person'): path(person)}
        account = old.get('/account')
        if account:
            values[slot('contact_organization')] = path('/' + account.split('/', 5)[5] if account.startswith('/h/') else account)
        if i < 9:
            office = directory + '/addresses/demo_office_' + str(i // 3 + 1)
            association = associations + '/' + ident + '_work'
            values[slot('contact_workplace')] = path(association)
            entity(association, 'Simulated workplace for ' + ident, is_synthetic=True, **{
                slot('association_contact'): path(target), slot('association_address'): path(office),
                slot('association_purpose'): path(directory + '/vocabulary/workplace'),
                slot('association_verification'): path(directory + '/vocabulary/demo_unverified'),
                slot('association_evidence'): path(evidence + '/association_' + ident)})
            entity(evidence + '/association_' + ident, 'Generated association ' + ident,
                   is_synthetic=True, source='generated_demo',
                   description='Simulated workplace association, not inferred from a map or employer.')
        add(target, values, 'poke')
    return records, associations


def address_selection(root, addresses, gather_formula):
    """A bounded table of independently readable address references.

    Pass its result as projections(..., address_table=result). This lets a CRM
    consume native /o addresses without scanning or copying the city catalog.
    """
    if len(addresses) > 64:
        raise ValueError('Select at most 64 addresses per CRM projection')
    records = [{'path': root + '/input', 'slots': {'/sys/lede': 'Selected address inputs'}},
               {'path': root + '/table', 'slots': {
                   '/sys/weft': gather_formula, '/sys/tack': reference(root + '/input', 'x'),
                   **{'address_' + str(i): reference(value, 'x') for i, value in enumerate(addresses)}}}]
    return records, '/x' + root + '/table'
