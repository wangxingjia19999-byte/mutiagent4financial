# Alpha101 101个因子全集

## Alpha_001
(rank(Ts_ArgMax(signed_power(((close - open) / (high - low + 1e-5)), 2), 12)) - 0.5)

## Alpha_002
(-1 * Ts_Rank(Delta(volume, 4), 18))

## Alpha_003
(-1 * Ts_Rank((close - vwap), 7))

## Alpha_004
Ts_Rank(volume, 9)

## Alpha_005
Ts_Rank((high - low), 5)

## Alpha_006
Ts_Rank(high, 5)

## Alpha_007
(-1 * Ts_Rank(low, 5))

## Alpha_008
Ts_Rank((open - Delay(close, 1)), 5)

## Alpha_009
Ts_Rank((volume / Ts_Mean(volume, 20)), 5)

## Alpha_010
(-1 * Ts_Rank(Return(close, 1), 10))

## Alpha_011
rank((close - Ts_Mean(close, 10)) / Ts_Mean(close, 10))

## Alpha_012
rank((high - Ts_Mean(close, 10)) / Ts_Mean(close, 10))

## Alpha_013
rank((Ts_Mean(close, 10) - open) / Ts_Mean(close, 10))

## Alpha_014
rank(Ts_Rank(close, 3) + Ts_Rank(close, 7) + Ts_Rank(close, 15))

## Alpha_015
rank(Ts_Sum(high - close, 5) / Ts_Sum(close - low, 5))

## Alpha_016
(-1 * rank(Ts_Corr(high, volume, 5)))

## Alpha_017
(-1 * rank(Ts_Corr(low, volume, 5)))

## Alpha_018
rank(Ts_Corr(Ts_Rank(volume, 5), Ts_Rank(high - low, 5), 5))

## Alpha_019
rank((high + low - close - open) / (high - low + 1e-5))

## Alpha_020
rank(Ts_Sum(volume * (close > open), 10) / Ts_Sum(volume, 10))

## Alpha_021
rank(Ts_Sum(volume * (close < open), 10) / Ts_Sum(volume, 10))

## Alpha_022
rank(Ts_Sum(Abs(close - open), 5) / Ts_Sum(high - low, 5))

## Alpha_023
rank(Ts_Sum((high - close) / (high - low + 1e-5), 20))

## Alpha_024
rank(Ts_Sum((close - low) / (high - low + 1e-5), 20))

## Alpha_025
rank(Ts_Sum(close > open, 10))

## Alpha_026
rank(Ts_Sum(close < open, 10))

## Alpha_027
rank(Ts_Sum(close > open, 3) - Ts_Sum(close < open, 3))

## Alpha_028
rank(Ts_Sum(close > open, 7) - Ts_Sum(close < open, 7))

## Alpha_029
rank(Ts_Sum(close > open, 15) - Ts_Sum(close < open, 15))

## Alpha_030
rank(Ts_Sum(close > open, 30) - Ts_Sum(close < open, 30))

## Alpha_031
rank(Ts_Sum(volume * (close > open), 5) / Ts_Sum(volume * (close < open), 5))

## Alpha_032
rank(Ts_Sum(volume * (close > open), 10) / Ts_Sum(volume * (close < open), 10))

## Alpha_033
rank(Ts_Sum(volume * (close > open), 20) / Ts_Sum(volume * (close < open), 20))

## Alpha_034
rank((high - Delay(high, 1)) / (high - low + 1e-5))

## Alpha_035
rank((low - Delay(low, 1)) / (high - low + 1e-5))

## Alpha_036
rank(Ts_Sum(close - Delay(close, 1), 5))

## Alpha_037
rank(Ts_Sum(close - Delay(close, 1), 10))

## Alpha_038
rank(Ts_Sum(close - Delay(close, 1), 20))

## Alpha_039
rank(Ts_Std(Return(close, 1), 5))

## Alpha_040
rank(Ts_Std(Return(close, 1), 10))

## Alpha_041
rank(Ts_Std(Return(close, 1), 20))

## Alpha_042
rank(Ts_Corr(close, volume, 5))

## Alpha_043
rank(Ts_Corr(close, volume, 10))

## Alpha_044
rank(Ts_Corr(close, volume, 20))

## Alpha_045
rank(Ts_Corr(vwap, volume, 5))

## Alpha_046
rank(Ts_Corr(vwap, volume, 10))

## Alpha_047
rank(Ts_Corr(vwap, volume, 20))

## Alpha_048
rank(Ts_Min(close, 5))

## Alpha_049
rank(Ts_Min(close, 10))

## Alpha_050
rank(Ts_Min(close, 20))

## Alpha_051
rank(Ts_Max(close, 5))

## Alpha_052
rank(Ts_Max(close, 10))

## Alpha_053
rank(Ts_Max(close, 20))

## Alpha_054
rank(Ts_Min(low, 5))

## Alpha_055
rank(Ts_Min(low, 10))

## Alpha_056
rank(Ts_Min(low, 20))

## Alpha_057
rank(Ts_Max(high, 5))

## Alpha_058
rank(Ts_Max(high, 10))

## Alpha_059
rank(Ts_Max(high, 20))

## Alpha_060
rank(Ts_Min(vwap, 5))

## Alpha_061
rank(Ts_Min(vwap, 10))

## Alpha_062
rank(Ts_Min(vwap, 20))

## Alpha_063
rank(Ts_Max(vwap, 5))

## Alpha_064
rank(Ts_Max(vwap, 10))

## Alpha_065
rank(Ts_Max(vwap, 20))

## Alpha_066
rank((close - Ts_Min(low, 5)) / (Ts_Max(high, 5) - Ts_Min(low, 5) + 1e-5))

## Alpha_067
rank((close - Ts_Min(low, 10)) / (Ts_Max(high, 10) - Ts_Min(low, 10) + 1e-5))

## Alpha_068
rank((close - Ts_Min(low, 20)) / (Ts_Max(high, 20) - Ts_Min(low, 20) + 1e-5))

## Alpha_069
rank((vwap - Ts_Min(low, 5)) / (Ts_Max(high, 5) - Ts_Min(low, 5) + 1e-5))

## Alpha_070
rank((vwap - Ts_Min(low, 10)) / (Ts_Max(high, 10) - Ts_Min(low, 10) + 1e-5))

## Alpha_071
rank((vwap - Ts_Min(low, 20)) / (Ts_Max(high, 20) - Ts_Min(low, 20) + 1e-5))

## Alpha_072
rank((close - Ts_Mean(close, 5)) / Ts_Mean(close, 5))

## Alpha_073
rank((close - Ts_Mean(close, 10)) / Ts_Mean(close, 10))

## Alpha_074
rank((close - Ts_Mean(close, 20)) / Ts_Mean(close, 20))

## Alpha_075
rank((vwap - Ts_Mean(vwap, 5)) / Ts_Mean(vwap, 5))

## Alpha_076
rank((vwap - Ts_Mean(vwap, 10)) / Ts_Mean(vwap, 10))

## Alpha_077
rank((vwap - Ts_Mean(vwap, 20)) / Ts_Mean(vwap, 20))

## Alpha_078
rank((volume - Ts_Mean(volume, 5)) / Ts_Mean(volume, 5))

## Alpha_079
rank((volume - Ts_Mean(volume, 10)) / Ts_Mean(volume, 10))

## Alpha_080
rank((volume - Ts_Mean(volume, 20)) / Ts_Mean(volume, 20))

## Alpha_081
rank(Ts_Rank(volume, 5) * Ts_Rank(Return(close, 1), 5))

## Alpha_082
rank(Ts_Rank(volume, 10) * Ts_Rank(Return(close, 1), 10))

## Alpha_083
rank(Ts_Rank(volume, 20) * Ts_Rank(Return(close, 1), 20))

## Alpha_084
rank(Ts_Rank(Ts_Sum(Return(close, 1), 5), 5) * Ts_Rank(volume, 5))

## Alpha_085
rank(Ts_Rank(Ts_Sum(Return(close, 1), 10), 10) * Ts_Rank(volume, 10))

## Alpha_086
rank(Ts_Rank(Ts_Sum(Return(close, 1), 20), 20) * Ts_Rank(volume, 20))

## Alpha_087
rank(Ts_Corr(Ts_Rank(close, 5), Ts_Rank(volume, 5), 5))

## Alpha_088
rank(Ts_Corr(Ts_Rank(close, 10), Ts_Rank(volume, 10), 10))

## Alpha_089
rank(Ts_Corr(Ts_Rank(close, 20), Ts_Rank(volume, 20), 20))

## Alpha_090
rank(Ts_Corr(Ts_Rank(vwap, 5), Ts_Rank(volume, 5), 5))

## Alpha_091
rank(Ts_Corr(Ts_Rank(vwap, 10), Ts_Rank(volume, 10), 10))

## Alpha_092
rank(Ts_Corr(Ts_Rank(vwap, 20), Ts_Rank(volume, 20), 20))

## Alpha_093
rank(Ts_Sum(close > Delay(close, 1), 5) / 5)

## Alpha_094
rank(Ts_Sum(close < Delay(close, 1), 5) / 5)

## Alpha_095
rank(Ts_Sum(close > Delay(close, 1), 10) / 10)

## Alpha_096
rank(Ts_Sum(close < Delay(close, 1), 10) / 10)

## Alpha_097
rank(Ts_Sum(close > Delay(close, 1), 20) / 20)

## Alpha_098
rank(Ts_Sum(close < Delay(close, 1), 20) / 20)

## Alpha_099
rank((high + low + close + open) / 4)

## Alpha_100
rank((high + low) / 2)

## Alpha_101
rank((close - vwap) / vwap)