//! The byte representation used by the Python incremental identity oracle.
//!
//! Successful native inputs use integral JSON numbers. The strict deserializer
//! rejects floating point and oversized integer tokens so their identity can be
//! computed by the Python fallback without relying on different float printers.

use std::fmt;

use serde::de::{self, MapAccess, SeqAccess, Visitor};
use serde::{Deserialize, Deserializer};
use serde_json::{Map, Value};
use sha2::{Digest, Sha256};

pub(crate) type Fingerprint = [u8; 32];

/// A JSON value that has no repeated object keys, at any nesting depth.
pub(crate) struct StrictValue(pub(crate) Value);

impl<'de> Deserialize<'de> for StrictValue {
    fn deserialize<D>(deserializer: D) -> Result<Self, D::Error>
    where
        D: Deserializer<'de>,
    {
        struct StrictVisitor;

        impl<'de> Visitor<'de> for StrictVisitor {
            type Value = StrictValue;

            fn expecting(&self, formatter: &mut fmt::Formatter) -> fmt::Result {
                formatter.write_str("a JSON value without duplicate object keys")
            }

            fn visit_unit<E: de::Error>(self) -> Result<Self::Value, E> {
                Ok(StrictValue(Value::Null))
            }

            fn visit_bool<E: de::Error>(self, value: bool) -> Result<Self::Value, E> {
                Ok(StrictValue(Value::Bool(value)))
            }

            fn visit_i64<E: de::Error>(self, value: i64) -> Result<Self::Value, E> {
                Ok(StrictValue(Value::Number(value.into())))
            }

            fn visit_u64<E: de::Error>(self, value: u64) -> Result<Self::Value, E> {
                Ok(StrictValue(Value::Number(value.into())))
            }

            fn visit_f64<E: de::Error>(self, _value: f64) -> Result<Self::Value, E> {
                Err(E::custom("floating-point or out-of-range JSON number is unsupported by the native identity index"))
            }

            fn visit_str<E: de::Error>(self, value: &str) -> Result<Self::Value, E> {
                Ok(StrictValue(Value::String(value.to_owned())))
            }

            fn visit_string<E: de::Error>(self, value: String) -> Result<Self::Value, E> {
                Ok(StrictValue(Value::String(value)))
            }

            fn visit_seq<A>(self, mut seq: A) -> Result<Self::Value, A::Error>
            where
                A: SeqAccess<'de>,
            {
                let mut values = Vec::new();
                while let Some(StrictValue(value)) = seq.next_element::<StrictValue>()? {
                    values.push(value);
                }
                Ok(StrictValue(Value::Array(values)))
            }

            fn visit_map<A>(self, mut map: A) -> Result<Self::Value, A::Error>
            where
                A: MapAccess<'de>,
            {
                let mut values = Map::new();
                while let Some(key) = map.next_key::<String>()? {
                    if values.contains_key(&key) {
                        return Err(de::Error::custom(format!("duplicate JSON key: {key}")));
                    }
                    let StrictValue(value) = map.next_value::<StrictValue>()?;
                    values.insert(key, value);
                }
                Ok(StrictValue(Value::Object(values)))
            }
        }

        deserializer.deserialize_any(StrictVisitor)
    }
}

pub(crate) fn digest_bytes(bytes: &[u8]) -> Fingerprint {
    Sha256::digest(bytes).into()
}

pub(crate) fn digest_value(value: &Value) -> Fingerprint {
    digest_bytes(&canonical_value(value))
}

pub(crate) fn hex(fingerprint: Fingerprint) -> String {
    let mut bytes = Vec::with_capacity(64);
    write_hex_digits(&fingerprint, &mut bytes);
    // The hexadecimal alphabet consists entirely of ASCII characters.
    String::from_utf8(bytes).expect("hexadecimal ASCII")
}

/// Write a fingerprint as 64 lowercase hexadecimal ASCII bytes.
pub(crate) fn write_hex(fingerprint: &Fingerprint, out: &mut Vec<u8>) {
    write_hex_digits(fingerprint, out);
}

const HEX: &[u8; 16] = b"0123456789abcdef";

fn write_hex_digits(fingerprint: &Fingerprint, out: &mut Vec<u8>) {
    let mut bytes = [0u8; 64];
    for (pair, byte) in bytes.chunks_exact_mut(2).zip(fingerprint) {
        pair[0] = HEX[(byte >> 4) as usize];
        pair[1] = HEX[(byte & 0xf) as usize];
    }
    out.extend_from_slice(&bytes);
}

/// Match json.dumps(sort_keys=True, separators=(',', ':'), ensure_ascii=True).
/// Numbers must satisfy the integer-only invariant enforced by StrictValue.
pub(crate) fn canonical_value(value: &Value) -> Vec<u8> {
    let mut out = Vec::new();
    write_value(value, &mut out);
    out
}

pub(crate) fn write_value(value: &Value, out: &mut Vec<u8>) {
    match value {
        Value::Null => out.extend_from_slice(b"null"),
        Value::Bool(false) => out.extend_from_slice(b"false"),
        Value::Bool(true) => out.extend_from_slice(b"true"),
        Value::Number(number) => {
            assert!(!number.is_f64(), "native canonical JSON requires integral numbers");
            out.extend_from_slice(number.to_string().as_bytes());
        }
        Value::String(string) => write_string(string, out),
        Value::Array(values) => {
            out.push(b'[');
            for (index, value) in values.iter().enumerate() {
                if index != 0 {
                    out.push(b',');
                }
                write_value(value, out);
            }
            out.push(b']');
        }
        Value::Object(values) => {
            // Sort explicitly, even if serde_json was built with preserve_order.
            // UTF-8's byte ordering preserves Unicode scalar ordering, matching
            // Python's lexicographic ordering for supported JSON strings.
            let mut keys: Vec<_> = values.keys().collect();
            keys.sort_unstable();
            out.push(b'{');
            for (index, key) in keys.into_iter().enumerate() {
                if index != 0 {
                    out.push(b',');
                }
                write_string(key, out);
                out.push(b':');
                write_value(&values[key], out);
            }
            out.push(b'}');
        }
    }
}

/// Write an ASCII JSON string using Python's lowercase UTF-16 escapes.
pub(crate) fn write_string(value: &str, out: &mut Vec<u8>) {
    out.push(b'"');
    for ch in value.chars() {
        match ch {
            '"' => out.extend_from_slice(b"\\\""),
            '\\' => out.extend_from_slice(b"\\\\"),
            '\u{08}' => out.extend_from_slice(b"\\b"),
            '\u{0c}' => out.extend_from_slice(b"\\f"),
            '\n' => out.extend_from_slice(b"\\n"),
            '\r' => out.extend_from_slice(b"\\r"),
            '\t' => out.extend_from_slice(b"\\t"),
            ' '..='~' => out.push(ch as u8),
            _ => {
                let mut units = [0; 2];
                for unit in ch.encode_utf16(&mut units) {
                    out.extend_from_slice(b"\\u");
                    out.push(HEX[(*unit >> 12) as usize]);
                    out.push(HEX[((*unit >> 8) & 0xf) as usize]);
                    out.push(HEX[((*unit >> 4) & 0xf) as usize]);
                    out.push(HEX[(*unit & 0xf) as usize]);
                }
            }
        }
    }
    out.push(b'"');
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;

    #[test]
    fn canonical_strings_match_python_ascii_encoding() {
        let value = json!({
            "z": "\u{0}\u{1}\u{8}\u{c}\n\r\t\"\\/\u{1f}\u{7f}\u{80}é𝄞😀",
            "a": [true, false, null, -1, 18446744073709551615u64],
        });
        assert_eq!(
            String::from_utf8(canonical_value(&value)).unwrap(),
            r#"{"a":[true,false,null,-1,18446744073709551615],"z":"\u0000\u0001\b\f\n\r\t\"\\/\u001f\u007f\u0080\u00e9\ud834\udd1e\ud83d\ude00"}"#
        );
    }

    #[test]
    fn canonical_object_keys_follow_unicode_scalar_order() {
        let value = json!({"😀": 1, "\u{e000}": 2, "é": 3, "a": 4});
        assert_eq!(
            String::from_utf8(canonical_value(&value)).unwrap(),
            r#"{"a":4,"\u00e9":3,"\ue000":2,"\ud83d\ude00":1}"#
        );
    }

    #[test]
    fn duplicate_keys_are_rejected_at_every_depth() {
        for input in [r#"{"x":1,"x":2}"#, r#"[{"x":{"y":1,"\u0079":2}}]"#] {
            let error = serde_json::from_str::<StrictValue>(input).err().unwrap();
            assert!(error.to_string().contains("duplicate JSON key"));
        }
        let StrictValue(value) = serde_json::from_str(r#"{"a":[{"b":1},{"b":2}]}"#).unwrap();
        assert_eq!(value, json!({"a": [{"b": 1}, {"b": 2}]}));
    }

    #[test]
    fn uncertain_numeric_forms_are_explicitly_unsupported() {
        for input in ["1.0", "1e3", "-0", "18446744073709551616", "-9223372036854775809"] {
            let error = serde_json::from_str::<StrictValue>(input).err().unwrap();
            assert!(error.to_string().contains("unsupported"), "{input}: {error}");
        }
        for input in ["0", "-1", "-9223372036854775808", "18446744073709551615"] {
            let StrictValue(value) = serde_json::from_str(input).unwrap();
            assert_eq!(canonical_value(&value), input.as_bytes());
        }
    }

    #[test]
    fn fingerprints_use_sha256_and_lowercase_hex() {
        assert_eq!(hex(digest_bytes(b"abc")), "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad");
        let fingerprint = digest_value(&json!(["anonymous"]));
        assert_eq!(hex(fingerprint), "f27b6edfcdcda907cc9b8d02ec488d9243e0e790292bd77365dc52cc48e94691");
        let mut written = Vec::new();
        write_hex(&fingerprint, &mut written);
        assert_eq!(written, hex(fingerprint).as_bytes());
    }
}
