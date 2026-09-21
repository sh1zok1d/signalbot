# D3 PATH_MORPHOLOGY

Adaptive discovery result. Not confirmatory.

## DISCOVERY_ID

```json
"D3"
```

## TERMINAL_CLASSIFICATION

```json
"NO_USEFUL_STRUCTURE"
```

## SPEC_AUTHORITY

```json
"docs/research/DISCOVERY_SPRINT_01_SPEC_COMPILATION.{json,md} superseded in place by DISCOVERY_SPRINT_01_RED_TEAM_REVIEW, DISCOVERY_SPRINT_01_PRE_EXECUTION_CORRECTION_D3_D4, and DISCOVERY_SPRINT_01_MECHANICAL_PRE_EXECUTION_FIX (latest explicit correction blocks are authority)"
```

## IMPLEMENTATION_COMMIT

```json
"26d8f7066533bcae7138d5a1952783f2a16f3c39"
```

## INTERVAL_USED

```json
"2020-02-01T00:05:00Z -> 2025-01-01T00:00:00Z exclusive"
```

## DATASET_IDENTITIES

```json
{
  "CORE_BTC_BINANCE_V0": "717d37a404f81eefd58c9a796cc11868c48226baf1de8ffecad5e5607f8dd415"
}
```

## SEEDS

```json
{
  "D3_NULL_SURROGATE_SEED": 20260921103
}
```

## ROW_COUNTS

```json
{
  "N": 1791
}
```

## YEAR_BREAKDOWN

```json
{
  "2020": 334,
  "2021": 364,
  "2022": 364,
  "2023": 364,
  "2024": 365
}
```

## PRIMARY_METRICS

```json
{
  "ALL_FUNCTIONAL_GATES_PASS": false,
  "BLOCK_LENGTH": 12,
  "FUNCTIONALS": [
    "MAX_UPSIDE_CLOSE_24H",
    "MAX_DOWNSIDE_CLOSE_24H",
    "TIME_TO_MAX_ABS_CLOSE_EXCURSION"
  ],
  "FUNCTIONAL_COUNT": 3,
  "MAX_DOWNSIDE_CLOSE_24H": {
    "COLLAPSED_TO_TERMINAL": false,
    "EMPIRICAL_MEAN": 0.02171903361463792,
    "GATE_PASS": false,
    "PRACTICAL_MAGNITUDE_MET": false,
    "STATISTICAL_THRESHOLD_MET": true,
    "SURROGATE_MEAN_MEDIAN": 0.02434383468987371,
    "SURROGATE_MEAN_P2_5": 0.02330173925570174,
    "SURROGATE_MEAN_P97_5": 0.025389474333927478,
    "TEMPORAL_CONSISTENCY_MET": true,
    "YEAR_BREAKDOWN": {
      "2020": {
        "mean": 0.021730205440567182,
        "same_direction": true
      },
      "2021": {
        "mean": 0.03218899655199739,
        "same_direction": false
      },
      "2022": {
        "mean": 0.02316474871156168,
        "same_direction": true
      },
      "2023": {
        "mean": 0.013120168627283168,
        "same_direction": true
      },
      "2024": {
        "mean": 0.018401084740823286,
        "same_direction": true
      }
    }
  },
  "MAX_UPSIDE_CLOSE_24H": {
    "COLLAPSED_TO_TERMINAL": false,
    "EMPIRICAL_MEAN": 0.022304736982664684,
    "GATE_PASS": false,
    "PRACTICAL_MAGNITUDE_MET": false,
    "STATISTICAL_THRESHOLD_MET": true,
    "SURROGATE_MEAN_MEDIAN": 0.025727281149207554,
    "SURROGATE_MEAN_P2_5": 0.02471378318164303,
    "SURROGATE_MEAN_P97_5": 0.026696858350148307,
    "TEMPORAL_CONSISTENCY_MET": true,
    "YEAR_BREAKDOWN": {
      "2020": {
        "mean": 0.024221609855904748,
        "same_direction": true
      },
      "2021": {
        "mean": 0.03068262538046164,
        "same_direction": false
      },
      "2022": {
        "mean": 0.019972961466594205,
        "same_direction": true
      },
      "2023": {
        "mean": 0.01660155685801789,
        "same_direction": true
      },
      "2024": {
        "mean": 0.02020867379570801,
        "same_direction": true
      }
    }
  },
  "TIME_TO_MAX_ABS_CLOSE_EXCURSION": {
    "COLLAPSED_TO_TERMINAL": false,
    "EMPIRICAL_MEAN": 195.4109436069235,
    "GATE_PASS": false,
    "PRACTICAL_MAGNITUDE_MET": false,
    "STATISTICAL_THRESHOLD_MET": true,
    "SURROGATE_MEAN_MEDIAN": 204.5745393634841,
    "SURROGATE_MEAN_P2_5": 201.46732272473477,
    "SURROGATE_MEAN_P97_5": 207.6002372975991,
    "TEMPORAL_CONSISTENCY_MET": true,
    "YEAR_BREAKDOWN": {
      "2020": {
        "mean": 188.9880239520958,
        "same_direction": true
      },
      "2021": {
        "mean": 192.7664835164835,
        "same_direction": true
      },
      "2022": {
        "mean": 195.03846153846155,
        "same_direction": true
      },
      "2023": {
        "mean": 196.21428571428572,
        "same_direction": true
      },
      "2024": {
        "mean": 203.4958904109589,
        "same_direction": true
      }
    }
  }
}
```

## BASELINE_METRICS

```json
{
  "BLOCK_LENGTH": 12,
  "COMPANIONS": {
    "24": {
      "ALL_FUNCTIONAL_GATES_PASS": false,
      "BLOCK_LENGTH": 24,
      "FUNCTIONALS": [
        "MAX_UPSIDE_CLOSE_24H",
        "MAX_DOWNSIDE_CLOSE_24H",
        "TIME_TO_MAX_ABS_CLOSE_EXCURSION"
      ],
      "FUNCTIONAL_COUNT": 3,
      "MAX_DOWNSIDE_CLOSE_24H": {
        "COLLAPSED_TO_TERMINAL": false,
        "EMPIRICAL_MEAN": 0.02171903361463792,
        "GATE_PASS": false,
        "PRACTICAL_MAGNITUDE_MET": false,
        "STATISTICAL_THRESHOLD_MET": true,
        "SURROGATE_MEAN_MEDIAN": 0.024091506034315334,
        "SURROGATE_MEAN_P2_5": 0.02302482804874426,
        "SURROGATE_MEAN_P97_5": 0.02515367051798069,
        "TEMPORAL_CONSISTENCY_MET": true,
        "YEAR_BREAKDOWN": {
          "2020": {
            "mean": 0.021730205440567182,
            "same_direction": true
          },
          "2021": {
            "mean": 0.03218899655199739,
            "same_direction": false
          },
          "2022": {
            "mean": 0.02316474871156168,
            "same_direction": true
          },
          "2023": {
            "mean": 0.013120168627283168,
            "same_direction": true
          },
          "2024": {
            "mean": 0.018401084740823286,
            "same_direction": true
          }
        }
      },
      "MAX_UPSIDE_CLOSE_24H": {
        "COLLAPSED_TO_TERMINAL": false,
        "EMPIRICAL_MEAN": 0.022304736982664684,
        "GATE_PASS": false,
        "PRACTICAL_MAGNITUDE_MET": false,
        "STATISTICAL_THRESHOLD_MET": true,
        "SURROGATE_MEAN_MEDIAN": 0.025247955967276768,
        "SURROGATE_MEAN_P2_5": 0.02412258541496124,
        "SURROGATE_MEAN_P97_5": 0.026327870534296704,
        "TEMPORAL_CONSISTENCY_MET": true,
        "YEAR_BREAKDOWN": {
          "2020": {
            "mean": 0.024221609855904748,
            "same_direction": true
          },
          "2021": {
            "mean": 0.03068262538046164,
            "same_direction": false
          },
          "2022": {
            "mean": 0.019972961466594205,
            "same_direction": true
          },
          "2023": {
            "mean": 0.01660155685801789,
            "same_direction": true
          },
          "2024": {
            "mean": 0.02020867379570801,
            "same_direction": true
          }
        }
      },
      "TIME_TO_MAX_ABS_CLOSE_EXCURSION": {
        "COLLAPSED_TO_TERMINAL": false,
        "EMPIRICAL_MEAN": 195.4109436069235,
        "GATE_PASS": false,
        "PRACTICAL_MAGNITUDE_MET": false,
        "STATISTICAL_THRESHOLD_MET": true,
        "SURROGATE_MEAN_MEDIAN": 202.5530429927415,
        "SURROGATE_MEAN_P2_5": 199.4032104969291,
        "SURROGATE_MEAN_P97_5": 205.85565326633167,
        "TEMPORAL_CONSISTENCY_MET": true,
        "YEAR_BREAKDOWN": {
          "2020": {
            "mean": 188.9880239520958,
            "same_direction": true
          },
          "2021": {
            "mean": 192.7664835164835,
            "same_direction": true
          },
          "2022": {
            "mean": 195.03846153846155,
            "same_direction": true
          },
          "2023": {
            "mean": 196.21428571428572,
            "same_direction": true
          },
          "2024": {
            "mean": 203.4958904109589,
            "same_direction": false
          }
        }
      }
    },
    "6": {
      "ALL_FUNCTIONAL_GATES_PASS": false,
      "BLOCK_LENGTH": 6,
      "FUNCTIONALS": [
        "MAX_UPSIDE_CLOSE_24H",
        "MAX_DOWNSIDE_CLOSE_24H",
        "TIME_TO_MAX_ABS_CLOSE_EXCURSION"
      ],
      "FUNCTIONAL_COUNT": 3,
      "MAX_DOWNSIDE_CLOSE_24H": {
        "COLLAPSED_TO_TERMINAL": false,
        "EMPIRICAL_MEAN": 0.02171903361463792,
        "GATE_PASS": false,
        "PRACTICAL_MAGNITUDE_MET": false,
        "STATISTICAL_THRESHOLD_MET": true,
        "SURROGATE_MEAN_MEDIAN": 0.024529018248312426,
        "SURROGATE_MEAN_P2_5": 0.023549159443020638,
        "SURROGATE_MEAN_P97_5": 0.025547296555782945,
        "TEMPORAL_CONSISTENCY_MET": true,
        "YEAR_BREAKDOWN": {
          "2020": {
            "mean": 0.021730205440567182,
            "same_direction": true
          },
          "2021": {
            "mean": 0.03218899655199739,
            "same_direction": false
          },
          "2022": {
            "mean": 0.02316474871156168,
            "same_direction": true
          },
          "2023": {
            "mean": 0.013120168627283168,
            "same_direction": true
          },
          "2024": {
            "mean": 0.018401084740823286,
            "same_direction": true
          }
        }
      },
      "MAX_UPSIDE_CLOSE_24H": {
        "COLLAPSED_TO_TERMINAL": false,
        "EMPIRICAL_MEAN": 0.022304736982664684,
        "GATE_PASS": false,
        "PRACTICAL_MAGNITUDE_MET": false,
        "STATISTICAL_THRESHOLD_MET": true,
        "SURROGATE_MEAN_MEDIAN": 0.026219810146348287,
        "SURROGATE_MEAN_P2_5": 0.02512918929921051,
        "SURROGATE_MEAN_P97_5": 0.027253606788199047,
        "TEMPORAL_CONSISTENCY_MET": true,
        "YEAR_BREAKDOWN": {
          "2020": {
            "mean": 0.024221609855904748,
            "same_direction": true
          },
          "2021": {
            "mean": 0.03068262538046164,
            "same_direction": false
          },
          "2022": {
            "mean": 0.019972961466594205,
            "same_direction": true
          },
          "2023": {
            "mean": 0.01660155685801789,
            "same_direction": true
          },
          "2024": {
            "mean": 0.02020867379570801,
            "same_direction": true
          }
        }
      },
      "TIME_TO_MAX_ABS_CLOSE_EXCURSION": {
        "COLLAPSED_TO_TERMINAL": false,
        "EMPIRICAL_MEAN": 195.4109436069235,
        "GATE_PASS": false,
        "PRACTICAL_MAGNITUDE_MET": false,
        "STATISTICAL_THRESHOLD_MET": true,
        "SURROGATE_MEAN_MEDIAN": 206.3819095477387,
        "SURROGATE_MEAN_P2_5": 203.4459240647683,
        "SURROGATE_MEAN_P97_5": 209.4076912339475,
        "TEMPORAL_CONSISTENCY_MET": true,
        "YEAR_BREAKDOWN": {
          "2020": {
            "mean": 188.9880239520958,
            "same_direction": true
          },
          "2021": {
            "mean": 192.7664835164835,
            "same_direction": true
          },
          "2022": {
            "mean": 195.03846153846155,
            "same_direction": true
          },
          "2023": {
            "mean": 196.21428571428572,
            "same_direction": true
          },
          "2024": {
            "mean": 203.4958904109589,
            "same_direction": true
          }
        }
      }
    }
  },
  "COMPANION_BLOCK_LENGTHS": [
    6,
    24
  ],
  "NULL": "5m_RETURN_TIME_OF_DAY_STRATIFIED_BLOCK_BOOTSTRAP"
}
```

## PROTOTYPE_GATE_FIELDS

```json
{
  "btc_side_used": false,
  "exactly_three_functionals": true,
  "high_low_used": false,
  "path_asymmetry_included": false,
  "practical_magnitude_threshold": "|emp_mean - surrogate_median| > 15% of |surrogate_median|",
  "statistical_threshold": "empirical mean outside surrogate-mean [2.5, 97.5]",
  "temporal_consistency_check": "at least 3 year-buckets same-direction vs surrogate median"
}
```

## SEARCH_SURFACE_ATTEMPTED

```json
[
  "MAX_UPSIDE_CLOSE_24H",
  "MAX_DOWNSIDE_CLOSE_24H",
  "TIME_TO_MAX_ABS_CLOSE_EXCURSION"
]
```

## FILES_OPENED

```json
[
  "artifacts/research_data/CORE_BTC_BINANCE_V0/canonical/1m/monthly/2020-01.parquet",
  "artifacts/research_data/CORE_BTC_BINANCE_V0/canonical/1m/monthly/2020-02.parquet",
  "artifacts/research_data/CORE_BTC_BINANCE_V0/canonical/1m/monthly/2020-03.parquet",
  "artifacts/research_data/CORE_BTC_BINANCE_V0/canonical/1m/monthly/2020-04.parquet",
  "artifacts/research_data/CORE_BTC_BINANCE_V0/canonical/1m/monthly/2020-05.parquet",
  "artifacts/research_data/CORE_BTC_BINANCE_V0/canonical/1m/monthly/2020-06.parquet",
  "artifacts/research_data/CORE_BTC_BINANCE_V0/canonical/1m/monthly/2020-07.parquet",
  "artifacts/research_data/CORE_BTC_BINANCE_V0/canonical/1m/monthly/2020-08.parquet",
  "artifacts/research_data/CORE_BTC_BINANCE_V0/canonical/1m/monthly/2020-09.parquet",
  "artifacts/research_data/CORE_BTC_BINANCE_V0/canonical/1m/monthly/2020-10.parquet",
  "artifacts/research_data/CORE_BTC_BINANCE_V0/canonical/1m/monthly/2020-11.parquet",
  "artifacts/research_data/CORE_BTC_BINANCE_V0/canonical/1m/monthly/2020-12.parquet",
  "artifacts/research_data/CORE_BTC_BINANCE_V0/canonical/1m/monthly/2021-01.parquet",
  "artifacts/research_data/CORE_BTC_BINANCE_V0/canonical/1m/monthly/2021-02.parquet",
  "artifacts/research_data/CORE_BTC_BINANCE_V0/canonical/1m/monthly/2021-03.parquet",
  "artifacts/research_data/CORE_BTC_BINANCE_V0/canonical/1m/monthly/2021-04.parquet",
  "artifacts/research_data/CORE_BTC_BINANCE_V0/canonical/1m/monthly/2021-05.parquet",
  "artifacts/research_data/CORE_BTC_BINANCE_V0/canonical/1m/monthly/2021-06.parquet",
  "artifacts/research_data/CORE_BTC_BINANCE_V0/canonical/1m/monthly/2021-07.parquet",
  "artifacts/research_data/CORE_BTC_BINANCE_V0/canonical/1m/monthly/2021-08.parquet",
  "artifacts/research_data/CORE_BTC_BINANCE_V0/canonical/1m/monthly/2021-09.parquet",
  "artifacts/research_data/CORE_BTC_BINANCE_V0/canonical/1m/monthly/2021-10.parquet",
  "artifacts/research_data/CORE_BTC_BINANCE_V0/canonical/1m/monthly/2021-11.parquet",
  "artifacts/research_data/CORE_BTC_BINANCE_V0/canonical/1m/monthly/2021-12.parquet",
  "artifacts/research_data/CORE_BTC_BINANCE_V0/canonical/1m/monthly/2022-01.parquet",
  "artifacts/research_data/CORE_BTC_BINANCE_V0/canonical/1m/monthly/2022-02.parquet",
  "artifacts/research_data/CORE_BTC_BINANCE_V0/canonical/1m/monthly/2022-03.parquet",
  "artifacts/research_data/CORE_BTC_BINANCE_V0/canonical/1m/monthly/2022-04.parquet",
  "artifacts/research_data/CORE_BTC_BINANCE_V0/canonical/1m/monthly/2022-05.parquet",
  "artifacts/research_data/CORE_BTC_BINANCE_V0/canonical/1m/monthly/2022-06.parquet",
  "artifacts/research_data/CORE_BTC_BINANCE_V0/canonical/1m/monthly/2022-07.parquet",
  "artifacts/research_data/CORE_BTC_BINANCE_V0/canonical/1m/monthly/2022-08.parquet",
  "artifacts/research_data/CORE_BTC_BINANCE_V0/canonical/1m/monthly/2022-09.parquet",
  "artifacts/research_data/CORE_BTC_BINANCE_V0/canonical/1m/monthly/2022-10.parquet",
  "artifacts/research_data/CORE_BTC_BINANCE_V0/canonical/1m/monthly/2022-11.parquet",
  "artifacts/research_data/CORE_BTC_BINANCE_V0/canonical/1m/monthly/2022-12.parquet",
  "artifacts/research_data/CORE_BTC_BINANCE_V0/canonical/1m/monthly/2023-01.parquet",
  "artifacts/research_data/CORE_BTC_BINANCE_V0/canonical/1m/monthly/2023-02.parquet",
  "artifacts/research_data/CORE_BTC_BINANCE_V0/canonical/1m/monthly/2023-03.parquet",
  "artifacts/research_data/CORE_BTC_BINANCE_V0/canonical/1m/monthly/2023-04.parquet",
  "artifacts/research_data/CORE_BTC_BINANCE_V0/canonical/1m/monthly/2023-05.parquet",
  "artifacts/research_data/CORE_BTC_BINANCE_V0/canonical/1m/monthly/2023-06.parquet",
  "artifacts/research_data/CORE_BTC_BINANCE_V0/canonical/1m/monthly/2023-07.parquet",
  "artifacts/research_data/CORE_BTC_BINANCE_V0/canonical/1m/monthly/2023-08.parquet",
  "artifacts/research_data/CORE_BTC_BINANCE_V0/canonical/1m/monthly/2023-09.parquet",
  "artifacts/research_data/CORE_BTC_BINANCE_V0/canonical/1m/monthly/2023-10.parquet",
  "artifacts/research_data/CORE_BTC_BINANCE_V0/canonical/1m/monthly/2023-11.parquet",
  "artifacts/research_data/CORE_BTC_BINANCE_V0/canonical/1m/monthly/2023-12.parquet",
  "artifacts/research_data/CORE_BTC_BINANCE_V0/canonical/1m/monthly/2024-01.parquet",
  "artifacts/research_data/CORE_BTC_BINANCE_V0/canonical/1m/monthly/2024-02.parquet",
  "artifacts/research_data/CORE_BTC_BINANCE_V0/canonical/1m/monthly/2024-03.parquet",
  "artifacts/research_data/CORE_BTC_BINANCE_V0/canonical/1m/monthly/2024-04.parquet",
  "artifacts/research_data/CORE_BTC_BINANCE_V0/canonical/1m/monthly/2024-05.parquet",
  "artifacts/research_data/CORE_BTC_BINANCE_V0/canonical/1m/monthly/2024-06.parquet",
  "artifacts/research_data/CORE_BTC_BINANCE_V0/canonical/1m/monthly/2024-07.parquet",
  "artifacts/research_data/CORE_BTC_BINANCE_V0/canonical/1m/monthly/2024-08.parquet",
  "artifacts/research_data/CORE_BTC_BINANCE_V0/canonical/1m/monthly/2024-09.parquet",
  "artifacts/research_data/CORE_BTC_BINANCE_V0/canonical/1m/monthly/2024-10.parquet",
  "artifacts/research_data/CORE_BTC_BINANCE_V0/canonical/1m/monthly/2024-11.parquet",
  "artifacts/research_data/CORE_BTC_BINANCE_V0/canonical/1m/monthly/2024-12.parquet"
]
```

## KNOWN_LIMITATIONS

```json
[
  "Adaptive discovery on historically exposed 2020-2024 data.",
  "Unconditional close-path design; not a terminal-return card."
]
```

## PROTECTED_2025_OPENED

```json
false
```

## PROTECTED_2026_OPENED

```json
false
```
