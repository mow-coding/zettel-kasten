from __future__ import annotations

import base64
from copy import deepcopy
import hashlib
import json
import sqlite3
import unittest
import zlib

from wom_kit import private_objet_metadata_index as contract
from wom_kit.private_objet_metadata_writer_contract import receipt_relative_path


_FIXED_VECTOR_B85 = (
    "c-rk+Tay#Z4SwHWvE{0~VNTyKyqzSKUvQqnQd8<~H9NufI5Xpg4aI+tdVCvS_5%0>2vA(iSlv>qrB9zU`|;}fdeX&PoWtbR_2hjs"
    "pT4X6-<EBC2R%-k@GtDAi)MlIWq&`-^#@GTJB)qP{&vS+^2v*`z6l++Bwsg+j&^xX&#tdO4u8|Pb6C_FyS{3h_f^xTdI2+%;xD!W"
    "u<CD{w(jq%cX(fQw;;4B#;iZR%83PQxrj1JZmbvDImH!cT6thP3ZJCm%s6IcR!)iFlki^W1eRy6Cp$$E=p=Q7*<i|vq8I>8Ox(-J"
    "lw>?c>y*w)D&<+^O8XF5)R46kA_+&T4U?dgVVs5F_ljDKSTFli6+t<dZAdzMu9y`jo2(+!ntQ>NrgPcgLjZ`7Q*?+Cz_BQ;_uP`!"
    "y^5|`wGk`QL@p%_TX#R>I@e35bL=5O5BrPUtRJM~eHCZWmHVXQbbVXL9@AK?Y!>^fPNVZ_uvRl?xK`3SP(G@_RW!lbBt_;S1{bAF"
    "f|(d{7Ab_Nm66OO=T$r~V*zvQ4o+5-w)NW*Kvk}1SR{(_->bh)|Mv3lzyC2>zS*Fv7t2*&E!(CnD8jS4$Cfr&Q6w}850@k?&#JD6"
    "el;9@(NNstzgOgegVXP1)7X;5YBoDGp=swZtN$|+s}?yvX7t$=>5&yXF*0#}u=}ALe&})0QI1y7#k#I$&3kN%ECs>w$%c3-qI*x="
    "kyS??Xc0P+DQ+0@{>|>oPosOBW2&L*@0WOdnY88VtlI)~^`LaMc(-WYFOJo|t?8^Sx#;ksDDLCC<7*ln`)!Lj$3_3(&U@L|%$LyC"
    "<#>2kCtOgj?XvmA-nB*T{Z4ixbk-joU2YZb`@v_NF@E;DYUhJZrmsQvFa<YXQFPx?2(0xUcz7ew-Iv(dBElHO56^!9Dx1t+@GW3$"
    "u;$zf=zEB_#kcEKCmz}wvVdiG+nhm0$C2RGh#)m%EG4N!O3V@-ifF7OAkQ)jCo?7|7(|9DGwYEcIDxV1(5z8KI&*(pok_)nMr7dH"
    "@I)9KBs#(-mz*IR2;7q~J`+?W49Xy&NKSgs5|dhrcoaNaJ@4v88eQDRo4Ll>k@F%f`&9{J7(!AoVW!MYnfQaTSLHYV=j3b%%^={c"
    "qH>mMN?zO--Sw|=2$1yFo>T06aVWUW#|Mz+*`?vo9e=LdhwQtn@%;!3AVyrCF=-?Cuw~geou!qagoQ+f-`i|Jq0>xwVT?$O0Y>Fg"
    "$b}zxF1Xez)4F7XQInCrPrJ`=#zk!d@9WUqm!*TOT_@hQcyDiOda(AmYF`&f8!B3Lhi$>IvIn;>*-Lg5b<HBLItViYnNt5B!L_~U"
    "14w&yeA@NDn^=8{0*dESK=09W2inN&RYuLT6W&RsMaVj2G&b_Y5MAb0(;a1rnn+>JOr&hMeKrLo)X{`D;55Z##;mll9BFUOV+xG^"
    "fFOzkE(;DsKDm+6F-lyNDF|VnK>>9z9t`(hIx^PlU>T9sL}8zZP+~BKhajWm+-EL~r;s#?_-*#+l!Nr$Q$RxL<dB%GF_gfH%cL+Q"
    "ZY|51?ka);lajYeI2$Z6_RJWO;%GGoX7I}>;9tZ)o<sgteRkCn>FiXg2m=NJS86?VIE(%XE*NIbDZThQ7WhojvnBN$?>iBCi1eKZ"
    "p5=UJPkhY!jw%H7w^fHko`C2@m76xyiQsk&jlX!}m+(aKo%2NTKjDc{<VfHFTnc9hCw)fb)aVO9FVGs22`pu0v`{9=$W1Z{h*=PU"
    "AmV7ggeNi%p2|E5E@F0x>b(ZV&=VIxYG{=J>U)!LoS6XLDPvT0QhU-*Fh1(q|16#;K7%Lzglyz$!@&-&o9h1_zFzNY>ZJ+CrK{rQ"
    "naZVu{NhAsPZPg@%zReho})P@MR4-^=D{j=GkLR<V^<^ce;i<!8){y9@^<-Y=%w4fiw{%zw+*nv$=c-gK7{zymM*RFiv*#29J#*Z"
    "!1^3V?XP4<bN8)Vgbt}*bo;HL3e)(q3^ISvr28D-h*RH;p=g%I!3Edh`ls=X+?!E)q9-HfXYh$S^vM&E@-uiu?^d1fj(1=0vu20D"
    "#F5L$<4FQ}xsz>5Q3Y+ht?%&k$eS7k8K(o^pYCluDn1`?sDe;KydbCC5ui4!MSnAS#a__!d8ps6>i(YoPhy2%BYnJ?ly|>3lTSrt"
    "mFm*B43Cejx|xu`ZW=U5T*wi_&YN-6+BTwNl+gnN!w<`*!=f+4tiu<3yLQO97wOy8TB0cpSX-5SN*<hU(qU||uZFS1xv$s#TIu5Y"
    "n%cFKEsD3sQxbYkZP(3aDmQrNxtBK_zhGCP3`55_EI*ln9m)+`4T8H#{#syYo7UH}k)^vmNlTG55xzvthmk^{K%+r=g_*h-L2XaW"
    "(lKIM*%+oXHAf}|v~-U~3F*vuM7hy&TG#nwKy$h5ImfrYY2xe+`js>PPdVc#Wt?}IL5GqzF$d(RT*}A|`0S{KHWsP(HPkEzPtCg)"
    "RwW$*1EuWO=gh?>3_p6s`ASDzE_?PO-z0r@%SN;P%`oF;a>?8pCUs|0Y5RPiK|A%Q2?SJ5Ea6$?ETVByGsC52tlSIn$Lx~9@}eK9"
    "!&lVbJ3+T=GpHP>nNRlNfenAwMCNk&^JCVWUs>}bW{t>_*q07knjk|~z$7@1(I&@DhytYm20E$Il2P#qDuGBT1tncnGCx0Sb}i8G"
    ";+(ubdWW@sUvO@`zWWh?^0I0j#PrmAe{_)1+ZH8qR7#*iBaEbgvnp!of-l3pXg$UtlZQ+J8na``l%Ehv6oy6_bSzKCKZ0;LGCOY#"
    "=fXa0jteYXiRi44G6%-dmkBi&q!R=<4NBXfbpXYA$UdS}5d#`yoFqIuH0QK`Ja3a^@(~vm_H8j3FCjDHiWxu)E_D#ua}$YRkdKIE"
    "Sd|Gx$zUC$Au0lfJ~)Sy-FuNwSD*e135t<2"
)


def _fixed_vector() -> dict[str, object]:
    raw = zlib.decompress(base64.b85decode(_FIXED_VECTOR_B85.encode("ascii")))
    if (
        len(raw) != 11_267
        or hashlib.sha256(raw).hexdigest()
        != "92116bf7670d37754a5745a8b8cd2df946a6b12dfb7feab982854050df7082c8"
    ):
        raise AssertionError("fixed vector bytes changed")
    return json.loads(raw)


def _nonempty_authority() -> tuple[dict[str, object], dict[str, object]]:
    vector = _fixed_vector()
    observations = deepcopy(vector["observations"])
    entries = sorted(
        (
            receipt_relative_path(observation["authority_key_sha256"]),
            observation["receipt_sha256"],
        )
        for observation in observations
    )
    authority = {
        "observations": observations,
        "private_manifest_state": "present_nonempty",
        "private_manifest_sha256": contract.sha256_digest(
            b"synthetic-private-manifest"
        ),
        "private_manifest_bytes": 26,
        "private_manifest_rows": 2,
        "receipt_inventory_state": "present_nonempty",
        "receipt_inventory_entries": entries,
        "receipt_inventory_sha256": contract.logical_row_digest(entries),
        "receipt_count": 2,
        "object_manifest_state": "present",
        "object_manifest_sha256": contract.sha256_digest(
            b"synthetic-object-manifest"
        ),
        "object_manifest_bytes": 25,
        "object_manifest_rows": 2,
        "writer_journal_state": "absent",
    }
    return authority, vector


class PrivateObjetMetadataIndexContractTests(unittest.TestCase):
    def test_manifest_and_canonical_row_framing_are_exact(self) -> None:
        self.assertEqual(28_859, len(contract.GENERATED_SCHEMA_MANIFEST_BYTES))
        self.assertEqual(
            contract.GENERATED_SCHEMA_MANIFEST_SHA256,
            contract.sha256_digest(contract.GENERATED_SCHEMA_MANIFEST_BYTES),
        )
        self.assertEqual(
            b'{"a":"\\u00e9","b":1}',
            contract.canonical_json_bytes({"b": 1, "a": "\u00e9"}),
        )
        self.assertEqual(b"", contract.logical_row_bytes(()))
        self.assertEqual(
            b'[1,"a"]\n[2,"b"]',
            contract.logical_row_bytes(((1, "a"), (2, "b"))),
        )
        manifest = contract.generated_schema_manifest()
        self.assertEqual(
            [12, 6, 8, 44],
            [
                len(table["columns"])
                for table in manifest["sqlite_contract"]["tables"]
            ],
        )
        self.assertEqual([], manifest["sqlite_contract"]["triggers"])
        self.assertEqual([], manifest["sqlite_contract"]["views"])
        self.assertNotIn(
            "IF NOT EXISTS", "\n".join(contract.PRIVATE_SCHEMA_STATEMENTS)
        )

    def test_both_empty_vectors_reproduce_exact_fingerprint_and_metadata(self) -> None:
        expected = {
            "absent": (
                2_203,
                "sha256:5f0d6ddd0167c3c368abcf1405370615184dce6346bbf17421841e0d0c735e3e",
                1_708,
                "sha256:cb3a65bf6bea0282c5ce58fed589df782040f1766843595fd28a18f35c43a5d7",
            ),
            "present_empty": (
                2_217,
                "sha256:b32eff237d0b398e5d7e1446077fd353dd457d9bbd91998a0a2770462d4b9108",
                1_715,
                "sha256:1265a01b5cc7b56917d9236eeb8f0a19cbc57e47b2dbdf6ac3053e6a9833b87e",
            ),
        }
        for state, evidence in expected.items():
            with self.subTest(state=state):
                projection = contract._compile_private_objet_index_projection(
                    contract.empty_private_objet_authority(state)
                )
                metadata_bytes = contract.canonical_json_bytes(
                    list(projection.metadata_row)
                )
                self.assertEqual(evidence[0], len(projection.authority_fingerprint_bytes))
                self.assertEqual(
                    evidence[1], projection.authority_fingerprint_sha256
                )
                self.assertEqual(evidence[2], len(metadata_bytes))
                self.assertEqual(
                    evidence[3], contract.sha256_digest(metadata_bytes)
                )
                self.assertEqual(44, len(projection.metadata_row))
                self.assertEqual((0, 0, 0, 0, 0, 0), projection.metadata_row[37:43])

    def test_n1_n2_reproduce_all_eleven_literal_rows(self) -> None:
        authority, vector = _nonempty_authority()
        projection = contract._compile_private_objet_index_projection(authority)
        self.assertEqual(
            tuple(tuple(row) for row in vector["observation_rows"]),
            projection.observation_rows,
        )
        self.assertEqual(
            tuple(tuple(row) for row in vector["alias_rows"]),
            projection.alias_rows,
        )
        self.assertEqual(
            tuple(tuple(row) for row in vector["projection_rows"]),
            projection.projection_rows,
        )
        row_set = vector["row_set_evidence"]
        for rows, digest_name, expected_name in (
            (
                projection.observation_rows,
                projection.observation_rows_sha256,
                "observation_rows",
            ),
            (projection.alias_rows, projection.alias_rows_sha256, "alias_rows"),
            (
                projection.projection_rows,
                projection.projection_rows_sha256,
                "projection_rows",
            ),
        ):
            evidence = row_set[expected_name]
            self.assertEqual(evidence["byte_count"], len(contract.logical_row_bytes(rows)))
            self.assertEqual(evidence["sha256"], digest_name)
        self.assertEqual((2, 5, 2, 4, 1, 2), projection.metadata_row[37:43])

    def test_unknown_or_malformed_authority_is_fail_closed(self) -> None:
        authority, _ = _nonempty_authority()
        cases = []
        extra = deepcopy(authority)
        extra["unknown"] = True
        cases.append(extra)
        wrong_key = deepcopy(authority)
        wrong_key["observations"][0]["authority_key_sha256"] = (
            "sha256:" + ("0" * 64)
        )
        cases.append(wrong_key)
        wrong_receipt = deepcopy(authority)
        wrong_receipt["receipt_inventory_entries"][0] = (
            wrong_receipt["receipt_inventory_entries"][0][0],
            "sha256:" + ("0" * 64),
        )
        wrong_receipt["receipt_inventory_sha256"] = contract.logical_row_digest(
            wrong_receipt["receipt_inventory_entries"]
        )
        cases.append(wrong_receipt)
        wrong_order = deepcopy(authority)
        wrong_order["receipt_inventory_entries"].reverse()
        wrong_order["receipt_inventory_sha256"] = contract.logical_row_digest(
            wrong_order["receipt_inventory_entries"]
        )
        cases.append(wrong_order)
        for candidate in cases:
            with self.subTest(case=cases.index(candidate)):
                with self.assertRaisesRegex(
                    contract.PrivateObjetIndexContractError,
                    "^private_objet_metadata_authority_invalid$",
                ):
                    contract._compile_private_objet_index_projection(candidate)

    def test_schema_rows_then_singleton_last_and_final_inspection(self) -> None:
        authority, _ = _nonempty_authority()
        projection = contract._compile_private_objet_index_projection(authority)
        conn = sqlite3.connect(":memory:")
        self.addCleanup(conn.close)
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("BEGIN IMMEDIATE")
        contract.replace_private_objet_index_rows(conn, projection)
        self.assertEqual(
            0,
            conn.execute(
                "SELECT COUNT(*) FROM private_objet_index_metadata"
            ).fetchone()[0],
        )
        self.assertTrue(conn.in_transaction)
        evidence = contract.insert_private_objet_index_metadata(conn, projection)
        self.assertEqual(2, evidence.observation_count)
        self.assertEqual(5, evidence.alias_count)
        self.assertEqual(4, evidence.projection_count)
        self.assertEqual([], conn.execute("PRAGMA foreign_key_check").fetchall())
        self.assertTrue(conn.in_transaction)
        conn.rollback()
        self.assertEqual(
            0,
            conn.execute(
                "SELECT COUNT(*) FROM sqlite_schema "
                "WHERE name='objet_source_metadata'"
            ).fetchone()[0],
        )

    def test_partial_schema_and_foreign_keys_off_fail_before_install(self) -> None:
        projection = contract._compile_private_objet_index_projection(
            contract.empty_private_objet_authority()
        )
        conn = sqlite3.connect(":memory:")
        self.addCleanup(conn.close)
        with self.assertRaises(contract.PrivateObjetIndexContractError):
            contract.install_private_objet_index_projection(conn, projection)
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("CREATE TABLE objet_source_metadata (wrong TEXT)")
        before = conn.execute(
            "SELECT sql FROM sqlite_schema WHERE name='objet_source_metadata'"
        ).fetchone()[0]
        with self.assertRaisesRegex(
            contract.PrivateObjetIndexContractError,
            "^private_objet_metadata_projection_invalid$",
        ):
            contract.install_private_objet_index_projection(conn, projection)
        after = conn.execute(
            "SELECT sql FROM sqlite_schema WHERE name='objet_source_metadata'"
        ).fetchone()[0]
        self.assertEqual(before, after)

    def test_install_requires_caller_transaction_and_rejects_private_view(
        self,
    ) -> None:
        projection = contract._compile_private_objet_index_projection(
            contract.empty_private_objet_authority()
        )
        conn = sqlite3.connect(":memory:")
        self.addCleanup(conn.close)
        conn.execute("PRAGMA foreign_keys=ON")
        with self.assertRaisesRegex(
            contract.PrivateObjetIndexContractError,
            "^private_objet_metadata_projection_invalid$",
        ):
            contract.install_private_objet_index_projection(conn, projection)

        conn.execute("BEGIN IMMEDIATE")
        contract.create_or_verify_private_objet_index_schema(conn)
        conn.execute(
            "CREATE VIEW leaked_private_view AS "
            "SELECT * FROM objet_source_metadata"
        )
        with self.assertRaisesRegex(
            contract.PrivateObjetIndexContractError,
            "^private_objet_metadata_projection_invalid$",
        ):
            contract.verify_private_objet_index_schema(conn)
        conn.rollback()

    def test_schema_rejects_public_trigger_that_reads_private_table(
        self,
    ) -> None:
        conn = sqlite3.connect(":memory:")
        self.addCleanup(conn.close)
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("BEGIN IMMEDIATE")
        contract.create_or_verify_private_objet_index_schema(conn)
        conn.execute(
            "CREATE TABLE public_probe(value TEXT)"
        )
        conn.execute(
            "CREATE TRIGGER public_private_bridge "
            "AFTER DELETE ON public_probe BEGIN "
            "INSERT INTO public_probe(value) "
            "SELECT alias_search_key FROM objet_name_aliases LIMIT 1; "
            "END"
        )
        with self.assertRaisesRegex(
            contract.PrivateObjetIndexContractError,
            "^private_objet_metadata_projection_invalid$",
        ):
            contract.verify_private_objet_index_schema(conn)
        conn.rollback()

    def test_metadata_digest_tamper_is_detected(self) -> None:
        authority, _ = _nonempty_authority()
        projection = contract._compile_private_objet_index_projection(authority)
        conn = sqlite3.connect(":memory:")
        self.addCleanup(conn.close)
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("BEGIN IMMEDIATE")
        contract.install_private_objet_index_projection(conn, projection)
        conn.execute(
            "UPDATE private_objet_index_metadata "
            "SET observation_rows_sha256=?",
            ("sha256:" + ("0" * 64),),
        )
        with self.assertRaisesRegex(
            contract.PrivateObjetIndexContractError,
            "^private_objet_metadata_projection_invalid$",
        ):
            contract.inspect_private_objet_index_semantics(conn)

    def test_coupled_alias_and_stored_digest_tamper_fails_expected_projection(
        self,
    ) -> None:
        authority, _ = _nonempty_authority()
        projection = contract._compile_private_objet_index_projection(authority)
        conn = sqlite3.connect(":memory:")
        self.addCleanup(conn.close)
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("BEGIN IMMEDIATE")
        contract.install_private_objet_index_projection(conn, projection)
        first_key, first_ordinal = conn.execute(
            "SELECT authority_key_sha256, alias_ordinal "
            "FROM objet_name_aliases "
            "ORDER BY authority_key_sha256, alias_ordinal LIMIT 1"
        ).fetchone()
        conn.execute(
            "UPDATE objet_name_aliases SET alias_search_key=? "
            "WHERE authority_key_sha256=? AND alias_ordinal=?",
            ("synthetic-coupled-alias", first_key, first_ordinal),
        )
        alias_rows = contract._fetch_rows(
            conn,
            "objet_name_aliases",
            contract.ALIAS_COLUMNS,
            (
                '"authority_key_sha256" COLLATE BINARY ASC, '
                '"alias_ordinal" COLLATE BINARY ASC'
            ),
        )
        conn.execute(
            "UPDATE private_objet_index_metadata "
            "SET alias_rows_sha256=?",
            (contract.logical_row_digest(alias_rows),),
        )
        contract.inspect_private_objet_index_semantics(conn)
        with self.assertRaisesRegex(
            contract.PrivateObjetIndexContractError,
            "^private_objet_metadata_projection_invalid$",
        ):
            contract.inspect_private_objet_index_semantics(
                conn,
                expected=projection,
            )


if __name__ == "__main__":
    unittest.main()
