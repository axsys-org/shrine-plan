  + myth_from_json
    \ value=json
    ^ maybe[goo_wire/myth]
    ?> (json/obj fields) value .none
    < entries
      | fields.stream.traverse_maybe
        \ field=jkv
        < pail (goo_wire/pail_from_json field.v)
        | ./some (goo_wire/myth_entry field.k pail)
    | ./some (goo_wire/myth entries.row)
  + pail_from_json
    \ value=json
    ^ maybe[goo_wire/pail]
    < kind (goo_wire/string (goo_wire/field "kind" value))
    = held (goo_wire/field "value" value)
      empty (goo_wire/pail .none .none .none .none .none .none .none)
    ? (eq kind "nat")
      < text (goo_wire/string held)
      | ./some empty.set_nat((./some text))
    ? (eq kind "bool")
      < b (goo_wire/boolean held)
      | ./some empty.set_boolean((./some b))
    ? (eq kind "text")
      < text (goo_wire/string held)
      | ./some empty.set_text((./some text))
    ? (eq kind "path")
      < text (goo_wire/string held)
      | ./some empty.set_path((./some text))
    ? (eq kind "weblink")
      < text (goo_wire/string held)
      | ./some empty.set_weblink((./some text))
    ? (eq kind "unsupported")
      < text (goo_wire/string (goo_wire/field "brand" held))
      | ./some empty.set_unsupported_brand((./some text))
    ? (eq kind "modifiers")
      < values (goo_wire/array held)
      < values (values.stream.traverse_maybe(goo_wire/string))
      | ./some empty.set_modifiers((./some (goo_wire/modifiers values.row)))
    .none
