"""Pure deterministic v0.3.297 private objet generated-index contracts.

The module deliberately owns no filesystem authority capture, lock lifecycle,
archive orchestration, or generic output.  Callers provide a closed, already
captured authority mapping.  This module revalidates the durable records,
compiles disposable rows, and installs or inspects those rows on a caller-owned
SQLite connection without committing or rolling back that connection.
"""

from __future__ import annotations

import base64
from collections.abc import Mapping, Sequence
from copy import deepcopy
from dataclasses import dataclass
import hashlib
import json
import re
import sqlite3
from typing import Any
import zlib

from .private_objet_metadata import (
    NAME_REASON_CODES,
    derive_filename_search_keys,
    project_objet_safe_label,
    validate_objet_safe_label_projection,
    validate_private_metadata_record,
)
from .private_objet_metadata_writer_contract import (
    authority_key_sha256,
    canonical_json_bytes as durable_canonical_json_bytes,
    receipt_relative_path,
)


GENERATED_SCHEMA_ID = "wom-kit/private-objet-generated-index/v0.1"
GENERATED_SCHEMA_MANIFEST_SCHEMA_ID = (
    "wom-kit/private-objet-generated-schema-manifest/v0.1"
)
GENERATED_SCHEMA_MANIFEST_SHA256 = (
    "sha256:a521cf945384ea8cb653fb39fdfec38821e6e0c549f4a2d57af4acb1dc89ef0a"
)
AUTHORITY_FINGERPRINT_SCHEMA_ID = (
    "wom-kit/private-objet-authority-fingerprint/v0.1"
)
SOURCE_SCHEMA_ID = "wom-kit/private-objet-source-metadata/v0.1"
SOURCE_SCHEMA_SHA256 = (
    "sha256:c5f2aae02b068bca976ed256e45bea33c8ec44e004df89adc4e15113c09c2150"
)
NORMALIZATION_PROFILE_ID = "wom-kit/filename-normalization/v0.1"
NORMALIZATION_PROFILE_SHA256 = (
    "sha256:efd98c04a3adbbabb6907b94f3cb0646be635f2f317d417ce79ba9befb58514c"
)
NORMALIZATION_HELPER_SHA256 = (
    "sha256:79081fd211d06705b06fe2123271c135bc6e9c4af2de5dc3331eddd51fb592c2"
)
UNICODE_VERSION = "17.0.0"
UNICODE_TABLE_SHA256 = (
    "sha256:62ad6ed6e49d5d4fe811907822fbff5949a0b86693c36c4196743cfcda06b036"
)
PROJECTION_SCHEMA_ID = "wom-kit/objet-safe-label-projection/v0.1"
PROJECTION_SCHEMA_SHA256 = (
    "sha256:baf23a8c453ffd61d32a9d6a7b9cf2024073d91aa821e7712190c28374952d66"
)
RECEIPT_SCHEMA_ID = (
    "wom-kit/private-objet-source-metadata-write-receipt/v0.1"
)
RECEIPT_SCHEMA_SHA256 = (
    "sha256:d56f48ba45094b9bd7fecebf3739700ecd7e4e02f607d709101e02bcf6dd0149"
)
AUTHORITY_CHAIN_SCHEMA_ID = (
    "wom-kit/private-objet-source-metadata-authority-chain/v0.1"
)
AUTHORITY_CHAIN_SCHEMA_SHA256 = (
    "sha256:b9704fabf8c718b79f21497cb4c163bb89eecc7ca7620f297a63c402e7155da9"
)
WRITER_CONTRACT_SOURCE_SHA256 = (
    "sha256:55f8b4bc23a146640669c231c9a1808de0458c420db95c4e40a9155f36403860"
)
EMPTY_SHA256 = (
    "sha256:e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
)

NORMALIZATION_PROFILE_VALUE = {
    "id": NORMALIZATION_PROFILE_ID,
    "unicode_version": UNICODE_VERSION,
    "confusables_data_sha256": None,
    "confusable_status": "not_checked",
}
NORMALIZATION_PROFILE_JSON = (
    '{"confusable_status":"not_checked","confusables_data_sha256":null,'
    '"id":"wom-kit/filename-normalization/v0.1","unicode_version":"17.0.0"}'
)

ALIAS_KIND_ORDER = (
    "filename_canonical_caseless",
    "filename_separator_folded",
    "stem_canonical_caseless",
    "stem_separator_folded",
    "extension_ascii_lower",
)
PRIVATE_AUDIENCES = ("private_archive", "restricted")

OBSERVATION_COLUMNS = (
    "authority_key_sha256",
    "object_id",
    "canonical_row_sha256",
    "observation_evidence_sha256",
    "receipt_sha256",
    "manifest_row_ordinal",
    "source_schema_id",
    "normalization_profile_id",
    "privacy_class",
    "alias_derivation_status",
    "alias_derivation_reason_codes_json",
    "label_candidate_count",
)
ALIAS_COLUMNS = (
    "authority_key_sha256",
    "object_id",
    "normalization_profile_id",
    "alias_ordinal",
    "alias_kind",
    "alias_search_key",
)
PROJECTION_COLUMNS = (
    "object_id",
    "audience",
    "projection_schema_id",
    "projection_json",
    "projection_sha256",
    "projection_status",
    "observation_count",
    "candidate_count",
)
METADATA_COLUMNS = (
    "singleton_id",
    "generated_schema_id",
    "generated_schema_manifest_schema_id",
    "generated_schema_manifest_sha256",
    "authority_fingerprint_schema_id",
    "private_authority_fingerprint_sha256",
    "private_manifest_state",
    "private_manifest_sha256",
    "private_manifest_bytes",
    "private_manifest_rows",
    "receipt_inventory_state",
    "receipt_inventory_sha256",
    "receipt_count",
    "object_manifest_state",
    "object_manifest_sha256",
    "object_manifest_bytes",
    "object_manifest_rows",
    "source_schema_id",
    "source_schema_sha256",
    "normalization_profile_id",
    "normalization_profile_json",
    "normalization_profile_sha256",
    "normalization_helper_sha256",
    "unicode_version",
    "unicode_table_sha256",
    "projection_schema_id",
    "projection_schema_sha256",
    "receipt_schema_id",
    "receipt_schema_sha256",
    "authority_chain_schema_id",
    "authority_chain_schema_sha256",
    "writer_contract_source_sha256",
    "writer_journal_state",
    "authority_state",
    "observation_rows_sha256",
    "alias_rows_sha256",
    "projection_rows_sha256",
    "observation_count",
    "alias_count",
    "distinct_object_count",
    "projection_count",
    "blocked_alias_derivation_count",
    "blocked_label_projection_count",
    "private_layer_complete",
)

PRIVATE_TABLE_NAMES = (
    "objet_source_metadata",
    "objet_name_aliases",
    "private_objet_label_projections",
    "private_objet_index_metadata",
)
PRIVATE_INDEX_NAMES = ("objet_name_aliases_lookup",)

_AUTHORITY_FIELDS = {
    "observations",
    "private_manifest_state",
    "private_manifest_sha256",
    "private_manifest_bytes",
    "private_manifest_rows",
    "receipt_inventory_state",
    "receipt_inventory_entries",
    "receipt_inventory_sha256",
    "receipt_count",
    "object_manifest_state",
    "object_manifest_sha256",
    "object_manifest_bytes",
    "object_manifest_rows",
    "writer_journal_state",
}
_OBSERVATION_FIELDS = {
    "manifest_row_ordinal",
    "authority_key_sha256",
    "canonical_row_sha256",
    "receipt_sha256",
    "source_record",
}
_DIGEST_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
_RECEIPT_PATH_RE = re.compile(
    r"^receipts/objects/private-source-metadata/[0-9a-f]{64}\.json$"
)


# The exact directive manifest is kept self-contained for Batch A.  Batch D
# supplies the byte-equal package resource; this compressed literal prevents a
# second hand-maintained DDL/manifest copy while preserving exact bytes.
_GENERATED_SCHEMA_MANIFEST_B85 = (
    "c-rk<ZFAc;68<Y3eUaUfTE2-CGfid^N9}o<b9#<5*G}xyfFx+Mktv6yoVuC(_X7x#B7p@6MY7|}B%dr|vAb9Ri^bvr@@a61Gn}Im"
    "$MYh(!q;e?#)Bt=kIU=v`?UP&CQolk;dmMTh0Ae6J5IA0|NYag`J*)$4HnDGG(wAczWg|k(@R{G^JtlsIf}}`lTQP*SdfAYWrHUP"
    "S`>IRz*(`%@f;OVnhu_n`HFl?a&(<$mqhko#WEYCJV$rMc#(`lTz<qj8)wULiE~1O7DQ%&ZxB&snHPg6@5t{FsdzCOlqg(a`svdk"
    "S}s=CSyhZy<<&Az%e(n|d^azykUjB84ce%vqzxVoB9tw&rWGxc0_Vg6=`x$++cd^mgg2!*j&OQYZa!S2EKO+pDU)R$*UBzeIjz?i"
    "cr?hC`88Uk|1j1!`7%itm=#qvkM8Et0u=@MO~_C&k8#x%l)5NUxdKaajEM1w^<!MjsU2zWpb#(Sq<wK3lfEN`tE{B9%Fs0?R;#*p"
    "zE<%Xmxxdy+Vq?-o`-kDfKm&-I6irP`X~A0`J1D`1>sqc9w9?1r8-daSNu07BxWh<+Mh?;_L0J7%n}=mv)}K@Fl~Mm80FCw<t{Xy"
    "{+L%(xcH)$kKPFy=$MApQ5dD&dbEmDI{c~;vZUXuvCtY*t<USeZxhy<x4+c`soh6xd{i?+GGf+FVa|-l#@B|cV8M1HM6+#LrDL&{"
    "@(QyR#E~p;Nr)<;kc$JpHj`JAsy66mgd{{R&WU-llIs{|FbU<RXBgQ=1nD0P7D%gvcV#t(g#v1>mdi@BTbvR5-Zesi65h|%Lu1{e"
    "f}X;6ZWaq#^554=0{*i5sbQ>e32@PRV!(wGwpVy@Lxyuxx*`h&@v!q-oEK@uuKrRjKk!t8=PBQwW<_a{bKih*7hR#WD?(D%)cr`x"
    "NR#Six_1A3`CsHSac4~jZ`f|S9QN)bz`2cN(-(F?j6wY?PKz?lh^p%`Q-5!<tUrZ|W%QoRSYdhO33%7lV#;RE0^L<sy1pUq1WR3D"
    "6%9$(PR<)?xVdb#SbV<tOp2;*(}>3y;kceib!1k2SfrH$-$Y{x5td$NbTuQrgFmcNBD@a5s)h*h(>rkm1w46=o8QMO+7PT4cEOYp"
    "34lm@NwbN~j!tLK&t}H)$;;UvhPcqr7t7`Q)s6A`1SmY<TRbwF_KggvHRNks_xdN*^l+evH`Z#<L5K1(C9STb<jR@IVie+WKCJMX"
    "_A?jxUg79{wGb|Fc3EB>K>8jUPYvHPo}aulid9&Y`2pN2Yh?J8cE~<F8TMD19vUaF&x~JRy?$W~e|Yyla~z;?a`D5EMx#ul#+afS"
    "Ejue^x9BtkLh-#Q8=~q_1FoWF0_oNQGK!SA*G!6<8ftd;IHG3V@*ZV)VwL>z?glTD187TC@h71ZCNUJ_4^bH}W@rDM%}xxauVvDI"
    "Ky*Qw!Tyy|j%&wWdDWpJ>S%MKpXi(&cZeGnolPF`QO3cri4uv+NpJCRWDIlCq&$s?haVowcY>_?Eh&v@rS<Ao)i{t<A)2xZm2LVr"
    "lC;9Ri{YX1`qWS{t%d8d{rMT=yXkOnzbf`PNY-?@S<!edU9vk18N3di&HgwWjI0q|ct;k$nsrJ|S}MsFh=l6=fk-c86hsn9j^X&^"
    "Z1(Hyv`Y&F(jr4e3@sA#$qA7{p03cKg%TKIH8`aK*+3E#oIQW>YG#0$598oGGr$$zpo&!f>g4UKSH|zB$NwhLhw<C&Pvhucv!maP"
    "gGaX99*$^Jnvu-u-_`kn7G$OpG<}rXJ(ktGwy1Pc_t^LmulTHKUH_wO&DRMGn3~{nzn=YqzV{PIFhzt|0<_qU5eE|`4LU%PyM`!C"
    "W;aR!1#KV5FxIjd0u-`k;3JVBMjxQCZzg79&4dG?p2@J+AdBho_T>0KZ)XNP&pH$;KiDAz-F}AxUJ+X>k!&6uo@X@XY-dAAfY^U3"
    "LdNzr$}4fwQ;UmwdrlKCWZWZSQx<-Lv0Go9C=ECji50D5lZ%TgZ~i@7uo1Y2o!xqdb+SR?%<2?#3(TZ*fW@3#Ep)ya2@xvr0v82!"
    "eNAz5E;>(^ix^jau_*Diq+V47)xm$4IHTEZc1k;6EI$&}4>x_nC&&)DM%bo1y{FyRRvQ*RqsZ?OY$2;C<Izcfazq;YjCKM~dz0~f"
    "W3ko7;%mf6-I?68?(X6h+Ttq5pa_*7o#SXLznMtt(XQcP7~A$%{6Hf)uM<PG()ZfbEnTZRzq~%39shcw(n}{)F-~W{%uZ(~N3%C@"
    "&SDqduTPA(zrUo;>U8$z?DY8PjDC7Kdo?4Uj-J0cdj4_-#!8<CNxr<E?+L<jLBTU+bVYpU$?KCDt(K7}xH@(t?v&}lzOHU)EK0uC"
    "3e!b*xkp6^v+mgo9|nHz0g&hfi9BXS9yBVeS8J9c5EQX5aM1T~Ay$p}&`o+nhv;n&z1}#Z1dprj%6L<uiOJTD<Nz{<#xuhNOJz%|"
    "K+<CpfL>)90h+^XM7?fh4q_a19j2G7<*MK_{p$rrI7k;48G(fJtDd`I*SkYh?+w?xp>_-?4ecxr4%8{MS?(ExQ$R^-9tfqRQ6$?T"
    "u#`H>FV97@ZQO1t>mKM8iz^>tVAf1}IA+<#CDfTIz$-`+R6F_)L7+T!r0_GM+WqnVSN2Gv%8C@-7yB+Tr>>R3+KZ!Wjw80oo$c-u"
    "fvB~EE@88wFGbZ4!{p)+5KStJJGd~R4Pqh<wqRJLJh2Ty$A@|-OdX~W{;9R__n|n&dDT~=XPWg_SBFSSM5){$O~rAmq8J7BqfsG8"
    "(_gFC_vo-t2S^Y?mU$XPW_wmr*K$La3-afj>|62mO?kHtBS8$Uar}nOahjv&4AeVFB!rq~&>s@5_znjAiarRY<6V(Ab)AV@#Xd6r"
    "6sM`do|19g8^DbOb1dsN)@QPQ<W3)Xw6gphlBd)>krb<GfR;LdY0-L}Vwu%IkTtVewk+r9=4O#b72fzCoG<5fkI;^28LzS#jLU|G"
    "K1?Z%5VsrnvPwGR9z>8sOFlrxS$N`jQ{N0MTh1LG^bi%;d;39|L6G;BX`@MEBZN&mG`(pUp}_ZWObW0&2{Ce<Xo@4(#ir@T$uvN5"
    "<YH@LSx#gIk!?-PJso$*VfK{Cr*pFT%aT>Wfbmsecs_V?KA=OmiY{<`J{YyBiaE8yy1nNN3{42qxT>e2RmG3P=vQ?u|3~vj^L+4m"
    "*mDD*Wo4Yi!89^m<e)eVQ5brG>4$-vI1#bC>xI~JNJk`&<;Sk&N7xTS6ofblC)0`LMnm;&f|evdFsD`$+m;oZo^MVF`vlvT?byB*"
    "S<WPkJRC$WO6(X<;>d9v3&(Lhv52U^j_jd$Gl6nvjUGxaDYWE!Hj2pzBI75BC$XF0sb!J2PHj60lVlRO0W!m>=LJsWc#&%bp6@zQ"
    "62-{$Leuevd&<?wZb!6K4T%vPG>zPelO(Zc#g2`F*h8daqQo|B*Yuq@un?Ns7WRG1CJl+~spGrB#E!j6RpF+E_5>YQmm|h&294g}"
    "HI0_i@x)8qX^7m38Mt8(#(qL-go)!jfp3~PihWF`tDShJA5;HiT6A(pi5JJF<px95l@ER8Hz8uhqETOYW29|+qO6;sFquZaH4XhB"
    "v59hi6uOb+Ibk>rFpeTWLcV94i5>XJb0XKYv2RT#F{+xOynWJ=HJK#S&<!Kf*_P{hu1Q88`C&x?vZm%V#-=+Vqrf)fFqjbk=9(xV"
    "QWA%dI#bUaN^Y`H5$m`^ywt*$*ec+dH_#IH$03Z~Ze3+j<G5OcTVS|4wKPu4g^M@95g|{~cRnc6YbXNW_EF|A^i`5o(umG>N*!=f"
    "TIXC(!mL%uhawys@RF0r5G3o-kiX>w#q?bYezU+aRNt}^*{kU}VNgbulM7$olFNnZIl0<*!PYsD1Idnb<6z+J5*L9hc5F`@&7d6@"
    "DP{07xgNqUs#l{r?WNG_nNlm7?xe=~qK)4nutjQ`DdQ+@XO~Z{7`(S4OnP@#;6?!GO?V^nv>D#OPNHd~RJ(dl*QZ3g17Ss;sT5gT"
    "NjBo3xyg4IL<4)RpJ8HQo<22f;|D`_3lws(q7NVUIiboY6EO$d*JZbDxKM)hSv!!BEG_k@Xg8w%1{>|E#9cK7J?-SlB)(DVdq5|*"
    "!))JqK7!FwdmHD3CfN<!!8D1;Zi?(>$fm}Pra|B(VPLzqkFaZD*K>m~aNG!yok9>;p+BA2;dC--FXZ<r0gh_+DQ1mE76+<wh(1#e"
    "$7izP_^fvTslB$go9}g*hx|D-cPpDehpkSd;fEu{^IyHEB(|z2Ka%c$ZbEWvtN#HCc}3x=2OZKbTT?|_KL`Pyn#<m@0Ey)fT*z<R"
    "0Z(4YiIoTZvX?O+%z)&r4AEM$*E6&<P}xfBdZ6UxjU8dR%GWt`$+eZ?U+@s=#Wy|VG~6p6YSf4>P^I6#(AyxrR9cQid_P2+TEV~X"
    "jS*=L{?!qcGO7tCdznNA@b06MzFx8eBB=Yw2}mM~c_qG5*ua8xy>Fx_Ye^qYQTlK0HI*H~Pu)jX81kuuQV?Jqz>QrV*1(V%5V8RT"
    "z3dKwkO%}&5PAyi5kAqYT0em4Tf$w`Ks7b=LV{o0KVGAC0kbD?>w%Dcn_!P_^SQWQei8Kxupu%@E!#>Zd_xctNi$hGs0Z<OKcEwd"
    "Mpc$+TZMK-sdR6@^V?2vyzLLwA{DNG3I8#{V7krGf>iE|m+9O{)A1JjLf1$Hi_YVl#o)j#)bbnm0osAp(Qz942KhYr3lJb6NJHHI"
    "p+jHqwxt4Yw1w114o^}wRn_eeg=vEH>%y8e)Vntv6w{7}LV+5|@lstT9mtfD(|v)fzW%Kj4Y%_U&@JwrBDEFv3-SU*tL$;_kT8DF"
    "%A>-1cB}gZktvl?nd!lxXG}vi`V7?Y!2oL=4ZD~%m0~h<8{Z`gPFtYh#2Z`fvr63;&>jV9uKg^5ZX>=jzD{t=x_Un@INsN|_9yNb"
    "+mH*br#rq7;>V=Hr{_I#_l^k^29TB-d%_Pg;XUw_9#tL|dDzuhf|SwJ_(3p>-MktHTa+m(M>#Tf_1k#g@s1L_W7kZN68YFw@jC{x"
    "4+Gh;mo^%*Q>zyj*`d})NOG#_V<kHk9|3BzJ0`#5C%@w-zvCw#C4O?d*C>Sl5r=z<qJzGaKS4ns<I2-Z5*Mw7-KO{>EBgF@yK2R&"
)

GENERATED_SCHEMA_MANIFEST_BYTES = zlib.decompress(
    base64.b85decode(_GENERATED_SCHEMA_MANIFEST_B85.encode("ascii"))
)
if (
    len(GENERATED_SCHEMA_MANIFEST_BYTES) != 28_859
    or hashlib.sha256(GENERATED_SCHEMA_MANIFEST_BYTES).hexdigest()
    != GENERATED_SCHEMA_MANIFEST_SHA256[7:]
):
    raise RuntimeError("private_objet_generated_schema_manifest_invalid")

_GENERATED_SCHEMA_MANIFEST = json.loads(
    GENERATED_SCHEMA_MANIFEST_BYTES.decode("ascii")
)
_TABLE_MANIFESTS = {
    table["name"]: table
    for table in _GENERATED_SCHEMA_MANIFEST["sqlite_contract"]["tables"]
}
_INDEX_MANIFESTS = {
    index["name"]: index
    for index in _GENERATED_SCHEMA_MANIFEST["sqlite_contract"]["indexes"]
}

OBJET_SOURCE_METADATA_DDL = _TABLE_MANIFESTS["objet_source_metadata"][
    "create_sql"
]
OBJET_NAME_ALIASES_DDL = _TABLE_MANIFESTS["objet_name_aliases"]["create_sql"]
OBJET_NAME_ALIASES_LOOKUP_DDL = _INDEX_MANIFESTS[
    "objet_name_aliases_lookup"
]["create_sql"]
PRIVATE_OBJET_LABEL_PROJECTIONS_DDL = _TABLE_MANIFESTS[
    "private_objet_label_projections"
]["create_sql"]
PRIVATE_OBJET_INDEX_METADATA_DDL = _TABLE_MANIFESTS[
    "private_objet_index_metadata"
]["create_sql"]
PRIVATE_SCHEMA_STATEMENTS = (
    OBJET_SOURCE_METADATA_DDL,
    OBJET_NAME_ALIASES_DDL,
    OBJET_NAME_ALIASES_LOOKUP_DDL,
    PRIVATE_OBJET_LABEL_PROJECTIONS_DDL,
    PRIVATE_OBJET_INDEX_METADATA_DDL,
)


class PrivateObjetIndexContractError(ValueError):
    """A fail-closed internal contract error with no private value in its text."""


@dataclass(frozen=True)
class PrivateObjetIndexProjection:
    """Immutable rows compiled from one complete authority snapshot."""

    observation_rows: tuple[tuple[Any, ...], ...]
    alias_rows: tuple[tuple[Any, ...], ...]
    projection_rows: tuple[tuple[Any, ...], ...]
    metadata_row: tuple[Any, ...]
    authority_fingerprint_bytes: bytes
    authority_fingerprint_sha256: str
    observation_rows_sha256: str
    alias_rows_sha256: str
    projection_rows_sha256: str


@dataclass(frozen=True)
class PrivateObjetIndexInspection:
    """Content-free semantic evidence from one caller-owned SQLite snapshot."""

    observation_count: int
    alias_count: int
    distinct_object_count: int
    projection_count: int
    blocked_alias_derivation_count: int
    blocked_label_projection_count: int
    observation_rows_sha256: str
    alias_rows_sha256: str
    projection_rows_sha256: str
    authority_fingerprint_sha256: str
    metadata_row: tuple[Any, ...]


def generated_schema_manifest() -> dict[str, Any]:
    """Return an isolated semantic copy of the exact generated-schema manifest."""

    return deepcopy(_GENERATED_SCHEMA_MANIFEST)


def _fail(code: str = "private_objet_metadata_authority_invalid") -> None:
    raise PrivateObjetIndexContractError(code)


def _contains_surrogate(value: Any) -> bool:
    if type(value) is str:
        return any(0xD800 <= ord(character) <= 0xDFFF for character in value)
    if type(value) in {list, tuple}:
        return any(_contains_surrogate(item) for item in value)
    if type(value) is dict:
        return any(
            _contains_surrogate(key) or _contains_surrogate(item)
            for key, item in value.items()
        )
    return False


def canonical_json_bytes(value: Any) -> bytes:
    """Return the exact v0.3.297 ASCII CJSON bytes without a terminal LF."""

    if _contains_surrogate(value):
        raise ValueError("private_objet_metadata_json_invalid")
    try:
        return json.dumps(
            value,
            sort_keys=True,
            ensure_ascii=True,
            allow_nan=False,
            separators=(",", ":"),
        ).encode("utf-8")
    except (TypeError, ValueError, UnicodeEncodeError) as exc:
        raise ValueError("private_objet_metadata_json_invalid") from exc


def sha256_digest(value: bytes) -> str:
    if type(value) is not bytes:
        raise TypeError("private_objet_metadata_digest_requires_bytes")
    return "sha256:" + hashlib.sha256(value).hexdigest()


def logical_row_bytes(rows: Sequence[Sequence[Any]]) -> bytes:
    """Frame positional JSON rows with LF only between adjacent rows."""

    if isinstance(rows, (str, bytes, bytearray)) or not isinstance(
        rows, Sequence
    ):
        raise TypeError("private_objet_metadata_rows_invalid")
    encoded: list[bytes] = []
    for row in rows:
        if isinstance(row, (str, bytes, bytearray)) or not isinstance(
            row, Sequence
        ):
            raise TypeError("private_objet_metadata_row_invalid")
        encoded.append(canonical_json_bytes(list(row)))
    return b"\n".join(encoded)


def logical_row_digest(rows: Sequence[Sequence[Any]]) -> str:
    return sha256_digest(logical_row_bytes(rows))


if canonical_json_bytes(_GENERATED_SCHEMA_MANIFEST) != (
    GENERATED_SCHEMA_MANIFEST_BYTES
):
    raise RuntimeError("private_objet_generated_schema_manifest_noncanonical")


def empty_private_objet_authority(
    receipt_inventory_state: str = "absent",
) -> dict[str, Any]:
    """Construct either normative closed zero-authority input."""

    if receipt_inventory_state not in {"absent", "present_empty"}:
        _fail()
    return {
        "observations": (),
        "private_manifest_state": "absent",
        "private_manifest_sha256": None,
        "private_manifest_bytes": 0,
        "private_manifest_rows": 0,
        "receipt_inventory_state": receipt_inventory_state,
        "receipt_inventory_entries": (),
        "receipt_inventory_sha256": EMPTY_SHA256,
        "receipt_count": 0,
        "object_manifest_state": "not_applicable_zero_private_rows",
        "object_manifest_sha256": None,
        "object_manifest_bytes": 0,
        "object_manifest_rows": 0,
        "writer_journal_state": "absent",
    }


def _is_digest(value: Any) -> bool:
    return type(value) is str and _DIGEST_RE.fullmatch(value) is not None


def _is_bounded_int(value: Any, minimum: int, maximum: int) -> bool:
    return type(value) is int and minimum <= value <= maximum


def _closed_mapping(value: Any, fields: set[str]) -> bool:
    return isinstance(value, Mapping) and set(value) == fields


def _validated_authority(
    authority: Mapping[str, Any],
) -> tuple[
    tuple[Mapping[str, Any], ...],
    tuple[tuple[str, str], ...],
    dict[str, Any],
]:
    if not _closed_mapping(authority, _AUTHORITY_FIELDS):
        _fail()

    observations_raw = authority["observations"]
    entries_raw = authority["receipt_inventory_entries"]
    if (
        isinstance(observations_raw, (str, bytes, bytearray))
        or not isinstance(observations_raw, Sequence)
        or isinstance(entries_raw, (str, bytes, bytearray))
        or not isinstance(entries_raw, Sequence)
    ):
        _fail()
    if len(observations_raw) > 100_000 or len(entries_raw) > 100_000:
        _fail()

    entries: list[tuple[str, str]] = []
    for raw_entry in entries_raw:
        if (
            isinstance(raw_entry, (str, bytes, bytearray))
            or not isinstance(raw_entry, Sequence)
            or len(raw_entry) != 2
        ):
            _fail()
        path, digest = raw_entry
        if (
            type(path) is not str
            or _RECEIPT_PATH_RE.fullmatch(path) is None
            or not _is_digest(digest)
        ):
            _fail()
        entries.append((path, digest))
    if entries != sorted(entries, key=lambda item: item[0].encode("utf-8")):
        _fail()
    if len({path for path, _ in entries}) != len(entries):
        _fail()

    receipt_inventory_sha256 = authority["receipt_inventory_sha256"]
    if (
        not _is_digest(receipt_inventory_sha256)
        or logical_row_digest(entries) != receipt_inventory_sha256
    ):
        _fail()

    observations: list[Mapping[str, Any]] = []
    seen_authority: set[str] = set()
    seen_evidence: set[str] = set()
    seen_rows: set[str] = set()
    receipt_by_path = dict(entries)
    for expected_ordinal, raw_observation in enumerate(
        observations_raw, start=1
    ):
        if not _closed_mapping(raw_observation, _OBSERVATION_FIELDS):
            _fail()
        ordinal = raw_observation["manifest_row_ordinal"]
        authority_key = raw_observation["authority_key_sha256"]
        canonical_row_sha256 = raw_observation["canonical_row_sha256"]
        receipt_sha256 = raw_observation["receipt_sha256"]
        record = raw_observation["source_record"]
        if (
            ordinal != expected_ordinal
            or not _is_bounded_int(ordinal, 1, 100_000)
            or not _is_digest(authority_key)
            or not _is_digest(canonical_row_sha256)
            or not _is_digest(receipt_sha256)
            or not validate_private_metadata_record(record)["accepted"]
        ):
            _fail()
        try:
            evidence = record["source_provenance"][
                "observation_evidence_sha256"
            ]
            recomputed_authority = authority_key_sha256(evidence)
            recomputed_row = sha256_digest(durable_canonical_json_bytes(record))
            expected_receipt_path = receipt_relative_path(authority_key)
        except (KeyError, TypeError, ValueError):
            _fail()
        if (
            not _is_digest(evidence)
            or authority_key != recomputed_authority
            or canonical_row_sha256 != recomputed_row
            or receipt_by_path.get(expected_receipt_path) != receipt_sha256
            or authority_key in seen_authority
            or evidence in seen_evidence
            or canonical_row_sha256 in seen_rows
        ):
            _fail()
        seen_authority.add(authority_key)
        seen_evidence.add(evidence)
        seen_rows.add(canonical_row_sha256)
        observations.append(raw_observation)

    scalar = {
        key: authority[key]
        for key in _AUTHORITY_FIELDS
        if key not in {"observations", "receipt_inventory_entries"}
    }
    integer_bounds = {
        "private_manifest_bytes": (0, 268_435_456),
        "private_manifest_rows": (0, 100_000),
        "receipt_count": (0, 100_000),
        "object_manifest_bytes": (0, 536_870_912),
        "object_manifest_rows": (0, 1_000_000),
    }
    if any(
        not _is_bounded_int(scalar[key], minimum, maximum)
        for key, (minimum, maximum) in integer_bounds.items()
    ):
        _fail()
    if (
        scalar["private_manifest_state"]
        not in {"absent", "present_nonempty"}
        or scalar["receipt_inventory_state"]
        not in {"absent", "present_empty", "present_nonempty"}
        or scalar["object_manifest_state"]
        not in {"not_applicable_zero_private_rows", "present"}
        or scalar["writer_journal_state"] != "absent"
        or scalar["private_manifest_rows"] != len(observations)
        or scalar["receipt_count"] != len(observations)
        or scalar["receipt_count"] != len(entries)
    ):
        _fail()

    if scalar["private_manifest_state"] == "absent":
        if (
            scalar["private_manifest_sha256"] is not None
            or scalar["private_manifest_bytes"] != 0
            or scalar["private_manifest_rows"] != 0
        ):
            _fail()
    elif (
        not _is_digest(scalar["private_manifest_sha256"])
        or scalar["private_manifest_bytes"] <= 0
        or scalar["private_manifest_rows"] <= 0
    ):
        _fail()

    receipt_state = scalar["receipt_inventory_state"]
    if receipt_state in {"absent", "present_empty"}:
        if (
            scalar["receipt_count"] != 0
            or entries
            or receipt_inventory_sha256 != EMPTY_SHA256
        ):
            _fail()
    elif scalar["receipt_count"] <= 0:
        _fail()

    if scalar["object_manifest_state"] == "not_applicable_zero_private_rows":
        if (
            scalar["object_manifest_sha256"] is not None
            or scalar["object_manifest_bytes"] != 0
            or scalar["object_manifest_rows"] != 0
        ):
            _fail()
    elif (
        not _is_digest(scalar["object_manifest_sha256"])
        or scalar["object_manifest_bytes"] <= 0
        or scalar["object_manifest_rows"] <= 0
    ):
        _fail()

    if observations:
        if (
            scalar["private_manifest_state"] != "present_nonempty"
            or receipt_state != "present_nonempty"
            or scalar["object_manifest_state"] != "present"
        ):
            _fail()
    elif (
        scalar["private_manifest_state"] != "absent"
        or receipt_state not in {"absent", "present_empty"}
        or scalar["object_manifest_state"]
        != "not_applicable_zero_private_rows"
    ):
        _fail()

    return tuple(observations), tuple(entries), scalar


def _fingerprint_payload(
    entries: tuple[tuple[str, str], ...],
    scalar: Mapping[str, Any],
) -> dict[str, Any]:
    private_state = scalar["private_manifest_state"]
    receipt_state = scalar["receipt_inventory_state"]
    object_state = scalar["object_manifest_state"]
    return {
        "schema": AUTHORITY_FINGERPRINT_SCHEMA_ID,
        "generated_schema": {
            "id": GENERATED_SCHEMA_ID,
            "manifest_schema_id": GENERATED_SCHEMA_MANIFEST_SCHEMA_ID,
            "manifest_sha256": GENERATED_SCHEMA_MANIFEST_SHA256,
        },
        "private_manifest": {
            "state": private_state,
            "state_marker": (
                "wom-kit/private-manifest/absent/v0.1"
                if private_state == "absent"
                else None
            ),
            "sha256": scalar["private_manifest_sha256"],
            "byte_count": scalar["private_manifest_bytes"],
            "row_count": scalar["private_manifest_rows"],
        },
        "receipt_inventory": {
            "state": receipt_state,
            "state_marker": {
                "absent": "wom-kit/receipt-inventory/absent/v0.1",
                "present_empty": (
                    "wom-kit/receipt-inventory/present-empty/v0.1"
                ),
                "present_nonempty": None,
            }[receipt_state],
            "count": scalar["receipt_count"],
            "entries": [list(entry) for entry in entries],
            "inventory_sha256": scalar["receipt_inventory_sha256"],
        },
        "object_manifest": {
            "state": object_state,
            "state_marker": (
                "wom-kit/object-manifest/not-applicable-zero-private-rows/v0.1"
                if object_state == "not_applicable_zero_private_rows"
                else None
            ),
            "sha256": scalar["object_manifest_sha256"],
            "byte_count": scalar["object_manifest_bytes"],
            "row_count": scalar["object_manifest_rows"],
        },
        "source_schema": {
            "id": SOURCE_SCHEMA_ID,
            "sha256": SOURCE_SCHEMA_SHA256,
        },
        "normalization": {
            "profile_id": NORMALIZATION_PROFILE_ID,
            "profile": deepcopy(NORMALIZATION_PROFILE_VALUE),
            "profile_sha256": NORMALIZATION_PROFILE_SHA256,
            "helper_sha256": NORMALIZATION_HELPER_SHA256,
            "unicode_version": UNICODE_VERSION,
            "unicode_table_sha256": UNICODE_TABLE_SHA256,
        },
        "projection_schema": {
            "id": PROJECTION_SCHEMA_ID,
            "sha256": PROJECTION_SCHEMA_SHA256,
        },
        "receipt_schema": {
            "id": RECEIPT_SCHEMA_ID,
            "sha256": RECEIPT_SCHEMA_SHA256,
        },
        "authority_chain_schema": {
            "id": AUTHORITY_CHAIN_SCHEMA_ID,
            "sha256": AUTHORITY_CHAIN_SCHEMA_SHA256,
        },
        "writer_contract": {
            "source_sha256": WRITER_CONTRACT_SOURCE_SHA256,
        },
        "writer_journal": {
            "state": "absent",
            "state_marker": "wom-kit/private-writer-journal/absent/v0.1",
        },
    }


def build_private_objet_authority_fingerprint(
    authority: Mapping[str, Any],
) -> tuple[bytes, str]:
    """Validate a closed authority and return exact payload bytes plus digest."""

    _, entries, scalar = _validated_authority(authority)
    encoded = canonical_json_bytes(_fingerprint_payload(entries, scalar))
    return encoded, sha256_digest(encoded)


def compile_private_objet_index_projection(
    authority: Mapping[str, Any],
) -> PrivateObjetIndexProjection:
    """Compile one complete closed authority snapshot into immutable SQL rows."""

    observations, entries, scalar = _validated_authority(authority)
    fingerprint_bytes = canonical_json_bytes(
        _fingerprint_payload(entries, scalar)
    )
    fingerprint_sha256 = sha256_digest(fingerprint_bytes)

    observation_rows: list[tuple[Any, ...]] = []
    alias_rows: list[tuple[Any, ...]] = []
    records_by_object: dict[str, list[tuple[int, Mapping[str, Any]]]] = {}

    for observation in observations:
        record = observation["source_record"]
        names = record["names"]
        alias_result = derive_filename_search_keys(names)
        if alias_result["issue_codes"]:
            _fail()
        alias_derivation_status = names["derivation_status"]
        reason_codes_json = canonical_json_bytes(
            names["reason_codes"]
        ).decode("ascii")
        emitted = alias_result["search_keys"]
        if (
            alias_derivation_status == "blocked"
            and emitted
            or alias_derivation_status == "valid"
            and not 1 <= len(emitted) <= 5
        ):
            _fail()

        evidence = record["source_provenance"][
            "observation_evidence_sha256"
        ]
        authority_key = observation["authority_key_sha256"]
        observation_rows.append(
            (
                authority_key,
                record["object_id"],
                observation["canonical_row_sha256"],
                evidence,
                observation["receipt_sha256"],
                observation["manifest_row_ordinal"],
                SOURCE_SCHEMA_ID,
                NORMALIZATION_PROFILE_ID,
                record["privacy_class"],
                alias_derivation_status,
                reason_codes_json,
                len(record["label_candidates"]),
            )
        )
        for ordinal, item in enumerate(emitted, start=1):
            if item["kind"] not in ALIAS_KIND_ORDER:
                _fail()
            alias_rows.append(
                (
                    authority_key,
                    record["object_id"],
                    NORMALIZATION_PROFILE_ID,
                    ordinal,
                    item["kind"],
                    item["value"],
                )
            )
        records_by_object.setdefault(record["object_id"], []).append(
            (observation["manifest_row_ordinal"], record)
        )

    observation_rows.sort(key=lambda row: row[0].encode("ascii"))
    alias_rows.sort(key=lambda row: (row[0].encode("ascii"), row[3]))

    projection_rows: list[tuple[Any, ...]] = []
    for object_id in sorted(records_by_object, key=lambda item: item.encode("ascii")):
        ordered = [
            record
            for _, record in sorted(
                records_by_object[object_id], key=lambda item: item[0]
            )
        ]
        if len(ordered) > 64:
            _fail()
        candidate_count = sum(
            len(record["label_candidates"]) for record in ordered
        )
        if candidate_count > 256:
            _fail()
        for audience in PRIVATE_AUDIENCES:
            result = project_objet_safe_label(ordered, audience, True)
            if result["issue_codes"] or "projection" not in result:
                _fail()
            projection = result["projection"]
            if not validate_objet_safe_label_projection(projection)["accepted"]:
                _fail()
            projection_bytes = canonical_json_bytes(projection)
            projection_rows.append(
                (
                    object_id,
                    audience,
                    PROJECTION_SCHEMA_ID,
                    projection_bytes.decode("ascii"),
                    sha256_digest(projection_bytes),
                    projection["status"],
                    len(ordered),
                    candidate_count,
                )
            )

    projection_rows.sort(
        key=lambda row: (row[0].encode("ascii"), row[1].encode("ascii"))
    )
    observation_tuple = tuple(observation_rows)
    alias_tuple = tuple(alias_rows)
    projection_tuple = tuple(projection_rows)
    observation_digest = logical_row_digest(observation_tuple)
    alias_digest = logical_row_digest(alias_tuple)
    projection_digest = logical_row_digest(projection_tuple)
    observation_count = len(observation_tuple)
    alias_count = len(alias_tuple)
    distinct_object_count = len(records_by_object)
    projection_count = len(projection_tuple)
    blocked_alias_count = sum(
        row[9] == "blocked" for row in observation_tuple
    )
    blocked_projection_count = sum(
        row[5] == "blocked" for row in projection_tuple
    )

    if (
        projection_count != 2 * distinct_object_count
        or not (
            observation_count - blocked_alias_count
            <= alias_count
            <= 5 * (observation_count - blocked_alias_count)
        )
    ):
        _fail()

    metadata_row = (
        1,
        GENERATED_SCHEMA_ID,
        GENERATED_SCHEMA_MANIFEST_SCHEMA_ID,
        GENERATED_SCHEMA_MANIFEST_SHA256,
        AUTHORITY_FINGERPRINT_SCHEMA_ID,
        fingerprint_sha256,
        scalar["private_manifest_state"],
        scalar["private_manifest_sha256"],
        scalar["private_manifest_bytes"],
        scalar["private_manifest_rows"],
        scalar["receipt_inventory_state"],
        scalar["receipt_inventory_sha256"],
        scalar["receipt_count"],
        scalar["object_manifest_state"],
        scalar["object_manifest_sha256"],
        scalar["object_manifest_bytes"],
        scalar["object_manifest_rows"],
        SOURCE_SCHEMA_ID,
        SOURCE_SCHEMA_SHA256,
        NORMALIZATION_PROFILE_ID,
        NORMALIZATION_PROFILE_JSON,
        NORMALIZATION_PROFILE_SHA256,
        NORMALIZATION_HELPER_SHA256,
        UNICODE_VERSION,
        UNICODE_TABLE_SHA256,
        PROJECTION_SCHEMA_ID,
        PROJECTION_SCHEMA_SHA256,
        RECEIPT_SCHEMA_ID,
        RECEIPT_SCHEMA_SHA256,
        AUTHORITY_CHAIN_SCHEMA_ID,
        AUTHORITY_CHAIN_SCHEMA_SHA256,
        WRITER_CONTRACT_SOURCE_SHA256,
        "absent",
        "empty_valid" if observation_count == 0 else "valid",
        observation_digest,
        alias_digest,
        projection_digest,
        observation_count,
        alias_count,
        distinct_object_count,
        projection_count,
        blocked_alias_count,
        blocked_projection_count,
        1,
    )
    if len(metadata_row) != 44:
        raise RuntimeError("private_objet_metadata_row_contract_invalid")
    return PrivateObjetIndexProjection(
        observation_rows=observation_tuple,
        alias_rows=alias_tuple,
        projection_rows=projection_tuple,
        metadata_row=metadata_row,
        authority_fingerprint_bytes=fingerprint_bytes,
        authority_fingerprint_sha256=fingerprint_sha256,
        observation_rows_sha256=observation_digest,
        alias_rows_sha256=alias_digest,
        projection_rows_sha256=projection_digest,
    )


def _quote_identifier(value: str) -> str:
    return '"' + value.replace('"', '""') + '"'


def _fetch_rows(
    conn: sqlite3.Connection,
    table: str,
    columns: tuple[str, ...],
    order_by: str,
) -> tuple[tuple[Any, ...], ...]:
    names = ", ".join(_quote_identifier(column) for column in columns)
    sql = (
        f"SELECT {names} FROM {_quote_identifier(table)} "
        f"ORDER BY {order_by}"
    )
    return tuple(tuple(row) for row in conn.execute(sql).fetchall())


def _private_schema_objects(
    conn: sqlite3.Connection,
) -> tuple[tuple[Any, ...], ...]:
    placeholders = ",".join("?" for _ in PRIVATE_TABLE_NAMES)
    sql = (
        "SELECT type, name, tbl_name, sql FROM sqlite_schema "
        f"WHERE name IN ({placeholders}) OR tbl_name IN ({placeholders}) "
        "ORDER BY type COLLATE BINARY, name COLLATE BINARY"
    )
    values = PRIVATE_TABLE_NAMES + PRIVATE_TABLE_NAMES
    return tuple(tuple(row) for row in conn.execute(sql, values).fetchall())


def _index_key_contract(
    conn: sqlite3.Connection,
    index_name: str,
) -> tuple[tuple[str, str, int], ...]:
    rows = conn.execute(
        f"PRAGMA index_xinfo({_quote_identifier(index_name)})"
    ).fetchall()
    return tuple(
        (row[2], row[4], row[3])
        for row in rows
        if row[5] == 1
    )


def verify_private_objet_index_schema(conn: sqlite3.Connection) -> None:
    """Require the complete exact four-table schema and no attached extras."""

    if not isinstance(conn, sqlite3.Connection):
        raise TypeError("private_objet_metadata_connection_invalid")
    objects = _private_schema_objects(conn)
    private_name_pattern = re.compile(
        r"\b(?:"
        + "|".join(re.escape(name) for name in PRIVATE_TABLE_NAMES)
        + r")\b",
        re.IGNORECASE,
    )
    for _object_type, executable_sql in conn.execute(
        "SELECT type, sql FROM sqlite_schema "
        "WHERE type IN ('trigger', 'view') AND sql IS NOT NULL "
        "ORDER BY type COLLATE BINARY, name COLLATE BINARY"
    ).fetchall():
        if private_name_pattern.search(executable_sql):
            _fail("private_objet_metadata_projection_invalid")
    sql_by_name = {
        name: (object_type, table_name, sql)
        for object_type, name, table_name, sql in objects
        if sql is not None
    }
    expected_sql = {
        "objet_source_metadata": ("table", "objet_source_metadata", OBJET_SOURCE_METADATA_DDL),
        "objet_name_aliases": ("table", "objet_name_aliases", OBJET_NAME_ALIASES_DDL),
        "private_objet_label_projections": (
            "table",
            "private_objet_label_projections",
            PRIVATE_OBJET_LABEL_PROJECTIONS_DDL,
        ),
        "private_objet_index_metadata": (
            "table",
            "private_objet_index_metadata",
            PRIVATE_OBJET_INDEX_METADATA_DDL,
        ),
        "objet_name_aliases_lookup": (
            "index",
            "objet_name_aliases",
            OBJET_NAME_ALIASES_LOOKUP_DDL,
        ),
    }
    if sql_by_name != expected_sql:
        _fail("private_objet_metadata_projection_invalid")

    for table in PRIVATE_TABLE_NAMES:
        actual_columns = [
            [
                row[1],
                row[2],
                row[3],
                row[4],
                row[5],
            ]
            for row in conn.execute(
                f"PRAGMA table_info({_quote_identifier(table)})"
            ).fetchall()
        ]
        if actual_columns != _TABLE_MANIFESTS[table]["columns"]:
            _fail("private_objet_metadata_projection_invalid")

    fk_rows = [
        list(row)
        for row in conn.execute(
            'PRAGMA foreign_key_list("objet_name_aliases")'
        ).fetchall()
    ]
    expected_fk_rows = [
        [
            0,
            0,
            "objet_source_metadata",
            "authority_key_sha256",
            "authority_key_sha256",
            "RESTRICT",
            "CASCADE",
            "NONE",
        ],
        [
            0,
            1,
            "objet_source_metadata",
            "object_id",
            "object_id",
            "RESTRICT",
            "CASCADE",
            "NONE",
        ],
        [
            0,
            2,
            "objet_source_metadata",
            "normalization_profile_id",
            "normalization_profile_id",
            "RESTRICT",
            "CASCADE",
            "NONE",
        ],
    ]
    if fk_rows != expected_fk_rows:
        _fail("private_objet_metadata_projection_invalid")
    for table in (
        "objet_source_metadata",
        "private_objet_label_projections",
        "private_objet_index_metadata",
    ):
        if conn.execute(
            f"PRAGMA foreign_key_list({_quote_identifier(table)})"
        ).fetchall():
            _fail("private_objet_metadata_projection_invalid")

    xinfo = [
        list(row)
        for row in conn.execute(
            'PRAGMA index_xinfo("objet_name_aliases_lookup")'
        ).fetchall()
    ]
    expected_xinfo = [
        [0, 5, "alias_search_key", 0, "BINARY", 1],
        [1, 1, "object_id", 0, "BINARY", 1],
        [2, 0, "authority_key_sha256", 0, "BINARY", 1],
        [3, 3, "alias_ordinal", 0, "BINARY", 1],
        [4, 4, "alias_kind", 0, "BINARY", 1],
        [5, -1, None, 0, "BINARY", 0],
    ]
    if xinfo != expected_xinfo:
        _fail("private_objet_metadata_projection_invalid")

    expected_unique = {
        table: {
            tuple((column, "BINARY", 0) for column in constraint)
            for constraint in _TABLE_MANIFESTS[table]["unique_constraints"]
        }
        for table in PRIVATE_TABLE_NAMES
    }
    expected_pk = {
        "objet_source_metadata": {
            (("authority_key_sha256", "BINARY", 0),)
        },
        "objet_name_aliases": {
            (
                ("authority_key_sha256", "BINARY", 0),
                ("alias_ordinal", "BINARY", 0),
            )
        },
        "private_objet_label_projections": {
            (
                ("object_id", "BINARY", 0),
                ("audience", "BINARY", 0),
            )
        },
        "private_objet_index_metadata": set(),
    }
    expected_created = {
        "objet_source_metadata": set(),
        "objet_name_aliases": {"objet_name_aliases_lookup"},
        "private_objet_label_projections": set(),
        "private_objet_index_metadata": set(),
    }
    for table in PRIVATE_TABLE_NAMES:
        index_rows = conn.execute(
            f"PRAGMA index_list({_quote_identifier(table)})"
        ).fetchall()
        if any(row[4] != 0 for row in index_rows):
            _fail("private_objet_metadata_projection_invalid")
        unique_contracts = {
            _index_key_contract(conn, row[1])
            for row in index_rows
            if row[3] == "u" and row[2] == 1
        }
        pk_contracts = {
            _index_key_contract(conn, row[1])
            for row in index_rows
            if row[3] == "pk" and row[2] == 1
        }
        created_names = {
            row[1]
            for row in index_rows
            if row[3] == "c"
        }
        if (
            unique_contracts != expected_unique[table]
            or pk_contracts != expected_pk[table]
            or created_names != expected_created[table]
        ):
            _fail("private_objet_metadata_projection_invalid")


def create_or_verify_private_objet_index_schema(
    conn: sqlite3.Connection,
) -> None:
    """Create the complete schema when absent, otherwise require exact equality."""

    if not isinstance(conn, sqlite3.Connection):
        raise TypeError("private_objet_metadata_connection_invalid")
    foreign_keys = conn.execute("PRAGMA foreign_keys").fetchone()
    if foreign_keys is None or foreign_keys[0] != 1:
        _fail("private_objet_metadata_projection_invalid")
    objects = _private_schema_objects(conn)
    if not objects:
        for statement in PRIVATE_SCHEMA_STATEMENTS:
            conn.execute(statement)
    verify_private_objet_index_schema(conn)


_INSERT_SQL = {
    "objet_source_metadata": (
        "INSERT INTO objet_source_metadata ("
        + ", ".join(OBSERVATION_COLUMNS)
        + ") VALUES ("
        + ",".join("?" for _ in OBSERVATION_COLUMNS)
        + ")"
    ),
    "objet_name_aliases": (
        "INSERT INTO objet_name_aliases ("
        + ", ".join(ALIAS_COLUMNS)
        + ") VALUES ("
        + ",".join("?" for _ in ALIAS_COLUMNS)
        + ")"
    ),
    "private_objet_label_projections": (
        "INSERT INTO private_objet_label_projections ("
        + ", ".join(PROJECTION_COLUMNS)
        + ") VALUES ("
        + ",".join("?" for _ in PROJECTION_COLUMNS)
        + ")"
    ),
    "private_objet_index_metadata": (
        "INSERT INTO private_objet_index_metadata ("
        + ", ".join(METADATA_COLUMNS)
        + ") VALUES ("
        + ",".join("?" for _ in METADATA_COLUMNS)
        + ")"
    ),
}


def replace_private_objet_index_rows(
    conn: sqlite3.Connection,
    projection: PrivateObjetIndexProjection,
) -> None:
    """Replace the three derived row sets and leave the singleton absent."""

    if not isinstance(projection, PrivateObjetIndexProjection):
        raise TypeError("private_objet_metadata_projection_invalid")
    if not conn.in_transaction:
        _fail("private_objet_metadata_projection_invalid")
    create_or_verify_private_objet_index_schema(conn)
    conn.execute("DELETE FROM objet_name_aliases")
    conn.execute("DELETE FROM objet_source_metadata")
    conn.execute("DELETE FROM private_objet_label_projections")
    conn.execute("DELETE FROM private_objet_index_metadata")
    conn.executemany(
        _INSERT_SQL["objet_source_metadata"], projection.observation_rows
    )
    conn.executemany(_INSERT_SQL["objet_name_aliases"], projection.alias_rows)
    conn.executemany(
        _INSERT_SQL["private_objet_label_projections"],
        projection.projection_rows,
    )
    actual_observations = _fetch_rows(
        conn,
        "objet_source_metadata",
        OBSERVATION_COLUMNS,
        '"authority_key_sha256" COLLATE BINARY ASC',
    )
    actual_aliases = _fetch_rows(
        conn,
        "objet_name_aliases",
        ALIAS_COLUMNS,
        (
            '"authority_key_sha256" COLLATE BINARY ASC, '
            '"alias_ordinal" COLLATE BINARY ASC'
        ),
    )
    actual_projections = _fetch_rows(
        conn,
        "private_objet_label_projections",
        PROJECTION_COLUMNS,
        (
            '"object_id" COLLATE BINARY ASC, '
            '"audience" COLLATE BINARY ASC'
        ),
    )
    if (
        actual_observations != projection.observation_rows
        or actual_aliases != projection.alias_rows
        or actual_projections != projection.projection_rows
        or conn.execute(
            "SELECT COUNT(*) FROM private_objet_index_metadata"
        ).fetchone()[0]
        != 0
        or conn.execute("PRAGMA foreign_key_check").fetchall()
    ):
        _fail("private_objet_metadata_projection_invalid")


def insert_private_objet_index_metadata(
    conn: sqlite3.Connection,
    projection: PrivateObjetIndexProjection,
) -> PrivateObjetIndexInspection:
    """Insert the singleton last and perform final semantic verification."""

    if not isinstance(projection, PrivateObjetIndexProjection):
        raise TypeError("private_objet_metadata_projection_invalid")
    if not conn.in_transaction:
        _fail("private_objet_metadata_projection_invalid")
    if (
        conn.execute(
            "SELECT COUNT(*) FROM private_objet_index_metadata"
        ).fetchone()[0]
        != 0
    ):
        _fail("private_objet_metadata_projection_invalid")
    conn.execute(
        _INSERT_SQL["private_objet_index_metadata"], projection.metadata_row
    )
    return inspect_private_objet_index_semantics(conn, expected=projection)


def install_private_objet_index_projection(
    conn: sqlite3.Connection,
    projection: PrivateObjetIndexProjection,
) -> PrivateObjetIndexInspection:
    """Install all rows without owning the caller's transaction lifecycle."""

    replace_private_objet_index_rows(conn, projection)
    return insert_private_objet_index_metadata(conn, projection)


def inspect_private_objet_index_semantics(
    conn: sqlite3.Connection,
    *,
    expected: PrivateObjetIndexProjection | None = None,
) -> PrivateObjetIndexInspection:
    """Verify exact schema, counts, row digests, and SQL-external invariants."""

    verify_private_objet_index_schema(conn)
    observation_rows = _fetch_rows(
        conn,
        "objet_source_metadata",
        OBSERVATION_COLUMNS,
        '"authority_key_sha256" COLLATE BINARY ASC',
    )
    alias_rows = _fetch_rows(
        conn,
        "objet_name_aliases",
        ALIAS_COLUMNS,
        (
            '"authority_key_sha256" COLLATE BINARY ASC, '
            '"alias_ordinal" COLLATE BINARY ASC'
        ),
    )
    projection_rows = _fetch_rows(
        conn,
        "private_objet_label_projections",
        PROJECTION_COLUMNS,
        (
            '"object_id" COLLATE BINARY ASC, '
            '"audience" COLLATE BINARY ASC'
        ),
    )
    metadata_rows = _fetch_rows(
        conn,
        "private_objet_index_metadata",
        METADATA_COLUMNS,
        '"singleton_id" COLLATE BINARY ASC',
    )
    if len(metadata_rows) != 1:
        _fail("private_objet_metadata_projection_invalid")
    metadata_row = metadata_rows[0]
    metadata = dict(zip(METADATA_COLUMNS, metadata_row, strict=True))

    observation_digest = logical_row_digest(observation_rows)
    alias_digest = logical_row_digest(alias_rows)
    projection_digest = logical_row_digest(projection_rows)
    observation_by_authority = {row[0]: row for row in observation_rows}
    if len(observation_by_authority) != len(observation_rows):
        _fail("private_objet_metadata_projection_invalid")

    ordinals: list[int] = []
    aliases_by_authority: dict[str, list[tuple[Any, ...]]] = {}
    for row in alias_rows:
        aliases_by_authority.setdefault(row[0], []).append(row)
    for row in observation_rows:
        (
            authority_key,
            _object_id,
            _canonical_row_sha256,
            evidence,
            _receipt_sha256,
            ordinal,
            source_schema_id,
            profile_id,
            _privacy_class,
            derivation_status,
            reason_json,
            _candidate_count,
        ) = row
        try:
            reasons = json.loads(reason_json)
        except (TypeError, ValueError):
            _fail("private_objet_metadata_projection_invalid")
        try:
            recomputed_authority_key = authority_key_sha256(evidence)
        except (TypeError, ValueError):
            _fail("private_objet_metadata_projection_invalid")
        if (
            recomputed_authority_key != authority_key
            or source_schema_id != SOURCE_SCHEMA_ID
            or profile_id != NORMALIZATION_PROFILE_ID
            or type(reasons) is not list
            or any(reason not in NAME_REASON_CODES for reason in reasons)
            or canonical_json_bytes(reasons).decode("ascii") != reason_json
        ):
            _fail("private_objet_metadata_projection_invalid")
        rows = aliases_by_authority.get(authority_key, [])
        if derivation_status == "blocked":
            if not reasons or rows:
                _fail("private_objet_metadata_projection_invalid")
        elif derivation_status == "valid":
            if reasons or not 1 <= len(rows) <= 5:
                _fail("private_objet_metadata_projection_invalid")
        else:
            _fail("private_objet_metadata_projection_invalid")
        if rows:
            kinds = [alias[4] for alias in rows]
            values = [alias[5] for alias in rows]
            if any(kind not in ALIAS_KIND_ORDER for kind in kinds):
                _fail("private_objet_metadata_projection_invalid")
            kind_positions = [ALIAS_KIND_ORDER.index(kind) for kind in kinds]
            if (
                [alias[3] for alias in rows] != list(range(1, len(rows) + 1))
                or kind_positions != sorted(set(kind_positions))
                or len(values) != len(set(values))
                or any(
                    alias[1] != row[1]
                    or alias[2] != NORMALIZATION_PROFILE_ID
                    for alias in rows
                )
            ):
                _fail("private_objet_metadata_projection_invalid")
        ordinals.append(ordinal)
    if sorted(ordinals) != list(range(1, len(observation_rows) + 1)):
        _fail("private_objet_metadata_projection_invalid")
    if any(key not in observation_by_authority for key in aliases_by_authority):
        _fail("private_objet_metadata_projection_invalid")

    projections_by_object: dict[str, list[tuple[Any, ...]]] = {}
    for row in projection_rows:
        projections_by_object.setdefault(row[0], []).append(row)
        try:
            projection_document = json.loads(row[3])
        except (TypeError, ValueError):
            _fail("private_objet_metadata_projection_invalid")
        projection_bytes = canonical_json_bytes(projection_document)
        if (
            projection_bytes.decode("ascii") != row[3]
            or sha256_digest(projection_bytes) != row[4]
            or not validate_objet_safe_label_projection(projection_document)[
                "accepted"
            ]
            or projection_document["object_id"] != row[0]
            or projection_document["audience"] != row[1]
            or projection_document["status"] != row[5]
        ):
            _fail("private_objet_metadata_projection_invalid")

    object_ids = {row[1] for row in observation_rows}
    if set(projections_by_object) != object_ids:
        _fail("private_objet_metadata_projection_invalid")
    for object_id, rows in projections_by_object.items():
        if (
            [row[1] for row in rows] != list(PRIVATE_AUDIENCES)
            or rows[0][6:] != rows[1][6:]
            or rows[0][6]
            != sum(row[1] == object_id for row in observation_rows)
        ):
            _fail("private_objet_metadata_projection_invalid")

    blocked_alias_count = sum(
        row[9] == "blocked" for row in observation_rows
    )
    blocked_projection_count = sum(
        row[5] == "blocked" for row in projection_rows
    )
    expected_constants = {
        "singleton_id": 1,
        "generated_schema_id": GENERATED_SCHEMA_ID,
        "generated_schema_manifest_schema_id": (
            GENERATED_SCHEMA_MANIFEST_SCHEMA_ID
        ),
        "generated_schema_manifest_sha256": (
            GENERATED_SCHEMA_MANIFEST_SHA256
        ),
        "authority_fingerprint_schema_id": AUTHORITY_FINGERPRINT_SCHEMA_ID,
        "source_schema_id": SOURCE_SCHEMA_ID,
        "source_schema_sha256": SOURCE_SCHEMA_SHA256,
        "normalization_profile_id": NORMALIZATION_PROFILE_ID,
        "normalization_profile_json": NORMALIZATION_PROFILE_JSON,
        "normalization_profile_sha256": NORMALIZATION_PROFILE_SHA256,
        "normalization_helper_sha256": NORMALIZATION_HELPER_SHA256,
        "unicode_version": UNICODE_VERSION,
        "unicode_table_sha256": UNICODE_TABLE_SHA256,
        "projection_schema_id": PROJECTION_SCHEMA_ID,
        "projection_schema_sha256": PROJECTION_SCHEMA_SHA256,
        "receipt_schema_id": RECEIPT_SCHEMA_ID,
        "receipt_schema_sha256": RECEIPT_SCHEMA_SHA256,
        "authority_chain_schema_id": AUTHORITY_CHAIN_SCHEMA_ID,
        "authority_chain_schema_sha256": AUTHORITY_CHAIN_SCHEMA_SHA256,
        "writer_contract_source_sha256": WRITER_CONTRACT_SOURCE_SHA256,
        "writer_journal_state": "absent",
        "private_layer_complete": 1,
    }
    actual_counts = {
        "observation_count": len(observation_rows),
        "alias_count": len(alias_rows),
        "distinct_object_count": len(object_ids),
        "projection_count": len(projection_rows),
        "blocked_alias_derivation_count": blocked_alias_count,
        "blocked_label_projection_count": blocked_projection_count,
    }
    metadata_state_valid = (
        metadata["private_manifest_rows"] == len(observation_rows)
        and metadata["receipt_count"] == len(observation_rows)
        and (
            metadata["private_manifest_state"] == "absent"
            and metadata["private_manifest_sha256"] is None
            and metadata["private_manifest_bytes"] == 0
            and metadata["private_manifest_rows"] == 0
            or metadata["private_manifest_state"] == "present_nonempty"
            and _is_digest(metadata["private_manifest_sha256"])
            and type(metadata["private_manifest_bytes"]) is int
            and metadata["private_manifest_bytes"] > 0
            and metadata["private_manifest_rows"] > 0
        )
        and (
            metadata["receipt_inventory_state"] in {"absent", "present_empty"}
            and metadata["receipt_count"] == 0
            or metadata["receipt_inventory_state"] == "present_nonempty"
            and metadata["receipt_count"] > 0
        )
        and _is_digest(metadata["receipt_inventory_sha256"])
        and (
            metadata["object_manifest_state"]
            == "not_applicable_zero_private_rows"
            and metadata["object_manifest_sha256"] is None
            and metadata["object_manifest_bytes"] == 0
            and metadata["object_manifest_rows"] == 0
            or metadata["object_manifest_state"] == "present"
            and _is_digest(metadata["object_manifest_sha256"])
            and type(metadata["object_manifest_bytes"]) is int
            and metadata["object_manifest_bytes"] > 0
            and metadata["object_manifest_rows"] > 0
        )
    )
    if (
        any(metadata[key] != value for key, value in expected_constants.items())
        or any(metadata[key] != value for key, value in actual_counts.items())
        or not metadata_state_valid
        or metadata["observation_rows_sha256"] != observation_digest
        or metadata["alias_rows_sha256"] != alias_digest
        or metadata["projection_rows_sha256"] != projection_digest
        or metadata["projection_count"] != 2 * metadata["distinct_object_count"]
        or not (
            metadata["observation_count"]
            - metadata["blocked_alias_derivation_count"]
            <= metadata["alias_count"]
            <= 5
            * (
                metadata["observation_count"]
                - metadata["blocked_alias_derivation_count"]
            )
        )
        or not _is_digest(metadata["private_authority_fingerprint_sha256"])
        or conn.execute("PRAGMA foreign_key_check").fetchall()
    ):
        _fail("private_objet_metadata_projection_invalid")

    if metadata["observation_count"] == 0:
        if (
            metadata["authority_state"] != "empty_valid"
            or metadata["private_manifest_state"] != "absent"
            or metadata["receipt_inventory_state"]
            not in {"absent", "present_empty"}
            or metadata["object_manifest_state"]
            != "not_applicable_zero_private_rows"
        ):
            _fail("private_objet_metadata_projection_invalid")
    elif (
        metadata["authority_state"] != "valid"
        or metadata["private_manifest_state"] != "present_nonempty"
        or metadata["receipt_inventory_state"] != "present_nonempty"
        or metadata["object_manifest_state"] != "present"
    ):
        _fail("private_objet_metadata_projection_invalid")

    if expected is not None:
        if (
            not isinstance(expected, PrivateObjetIndexProjection)
            or observation_rows != expected.observation_rows
            or alias_rows != expected.alias_rows
            or projection_rows != expected.projection_rows
            or metadata_row != expected.metadata_row
        ):
            _fail("private_objet_metadata_projection_invalid")

    return PrivateObjetIndexInspection(
        observation_count=len(observation_rows),
        alias_count=len(alias_rows),
        distinct_object_count=len(object_ids),
        projection_count=len(projection_rows),
        blocked_alias_derivation_count=blocked_alias_count,
        blocked_label_projection_count=blocked_projection_count,
        observation_rows_sha256=observation_digest,
        alias_rows_sha256=alias_digest,
        projection_rows_sha256=projection_digest,
        authority_fingerprint_sha256=metadata[
            "private_authority_fingerprint_sha256"
        ],
        metadata_row=metadata_row,
    )
