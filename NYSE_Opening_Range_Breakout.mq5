//+------------------------------------------------------------------+
//|                                  NYSE_Opening_Range_Breakout.mq5 |
//|                                  NYSE Opening Range Breakout EA  |
//|                                                                  |
//+------------------------------------------------------------------+
#property copyright "NYSE Opening Range Breakout Strategy"
#property link      ""
#property version   "1.00"

//--- Input Parameters
input string   InputSymbol = "NAS100";           // Trading Symbol (NAS100/US100/NQ1!)
input int      MagicNumber = 123456;            // Magic Number
input double   FixedRiskUSD = 100.0;            // Fixed Risk Amount in USD per trade
input bool     UseTrailingStop = false;         // Use Trailing Stop Loss
input double   TrailingStopRatio = 0.15;        // Trailing Stop Ratio (0.15R)
input int      SessionStartHour = 9;            // Session Start Hour (NY time)
input int      SessionStartMinute = 45;         // Session Start Minute
input int      SessionEndHour = 14;             // Session End Hour (NY time)
input int      SessionEndMinute = 45;           // Session End Minute
input int      OpeningRangeStartHour = 9;       // Opening Range Start Hour (NY time)
input int      OpeningRangeStartMinute = 30;    // Opening Range Start Minute
input int      OpeningRangeEndMinute = 45;      // Opening Range End Minute
input double   RiskRewardRatio = 1.4;           // Risk/Reward Ratio (TP = SL * 1.4)
input bool     TradeOnNewsDays = true;          // Trade on High Impact News Days (NFP, CPI)

//--- Global Variables
double g_OpeningRangeHigh = 0.0;
double g_OpeningRangeLow = 0.0;
bool g_OpeningRangeSet = false;
bool g_BreakoutDetected = false;
datetime g_LastBarTime = 0;
datetime g_OpeningRangeBarTime = 0;
int g_CurrentDay = 0;
string g_TradingSymbol = "";

//+------------------------------------------------------------------+
//| Expert initialization function                                   |
//+------------------------------------------------------------------+
int OnInit()
{
   // Normalize symbol name
   g_TradingSymbol = InputSymbol;
   if(StringFind(InputSymbol, "!") == -1 && StringFind(InputSymbol, ".") == -1)
   {
      // Try common variations
      if(StringFind(InputSymbol, "NAS") != -1 || StringFind(InputSymbol, "NQ") != -1)
      {
         g_TradingSymbol = "NAS100";
         if(!SymbolSelect(g_TradingSymbol, true))
         {
            g_TradingSymbol = "US100";
            if(!SymbolSelect(g_TradingSymbol, true))
            {
               g_TradingSymbol = "NQ1!";
               SymbolSelect(g_TradingSymbol, true);
            }
         }
      }
   }
   else
   {
      SymbolSelect(g_TradingSymbol, true);
   }
   
   // Verify symbol is available
   if(!SymbolInfoInteger(g_TradingSymbol, SYMBOL_SELECT))
   {
      Print("ERROR: Symbol ", g_TradingSymbol, " is not available. Please add it to Market Watch.");
      return(INIT_FAILED);
   }
   
   // Initialize variables
   g_CurrentDay = Day();
   g_OpeningRangeSet = false;
   g_BreakoutDetected = false;
   g_LastBarTime = 0;
   
   Print("NYSE Opening Range Breakout EA initialized");
   Print("Trading Symbol: ", g_TradingSymbol);
   Print("Fixed Risk per Trade: $", FixedRiskUSD);
   Print("Session: ", SessionStartHour, ":", StringFormat("%02d", SessionStartMinute), 
         " - ", SessionEndHour, ":", StringFormat("%02d", SessionEndMinute), " (NY Time)");
   
   return(INIT_SUCCEEDED);
}

//+------------------------------------------------------------------+
//| Expert deinitialization function                                 |
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
{
   Print("NYSE Opening Range Breakout EA deinitialized. Reason: ", reason);
}

//+------------------------------------------------------------------+
//| Expert tick function                                             |
//+------------------------------------------------------------------+
void OnTick()
{
   // Check if new bar formed
   datetime currentBarTime = iTime(g_TradingSymbol, PERIOD_M15, 0);
   if(currentBarTime == g_LastBarTime)
      return; // No new bar
   
   g_LastBarTime = currentBarTime;
   
   // Check if it's a new trading day
   MqlDateTime dt;
   TimeToStruct(TimeCurrent(), dt);
   int currentDay = dt.day;
   if(currentDay != g_CurrentDay)
   {
      // Reset for new day
      g_CurrentDay = currentDay;
      g_OpeningRangeSet = false;
      g_BreakoutDetected = false;
      g_OpeningRangeBarTime = 0;
      Print("New trading day detected. Resetting opening range.");
   }
   
   // Check if we're in trading session (NY time)
   if(!IsInTradingSession())
      return;
   
   // Check if it's a trading day (Monday-Friday or news day)
   if(!IsTradingDay())
      return;
   
   // Step 1 & 2: Wait for opening range candle (09:30-09:45 NY time) to close
   if(!g_OpeningRangeSet)
   {
      if(IsOpeningRangeCandle(currentBarTime))
      {
         // Get the opening range candle
         double high = iHigh(g_TradingSymbol, PERIOD_M15, 0);
         double low = iLow(g_TradingSymbol, PERIOD_M15, 0);
         
         // Wait for candle to close (check previous bar)
         datetime prevBarTime = iTime(g_TradingSymbol, PERIOD_M15, 1);
         if(prevBarTime > 0 && IsOpeningRangeCandle(prevBarTime))
         {
            g_OpeningRangeHigh = iHigh(g_TradingSymbol, PERIOD_M15, 1);
            g_OpeningRangeLow = iLow(g_TradingSymbol, PERIOD_M15, 1);
            g_OpeningRangeSet = true;
            g_OpeningRangeBarTime = prevBarTime;
            
            Print("Opening Range Set:");
            Print("  High: ", g_OpeningRangeHigh);
            Print("  Low: ", g_OpeningRangeLow);
            Print("  Time: ", TimeToString(g_OpeningRangeBarTime, TIME_DATE|TIME_MINUTES));
         }
      }
      return;
   }
   
   // Step 3 & 4: Wait for breakout candle to close
   if(g_OpeningRangeSet && !g_BreakoutDetected)
   {
      // Check if we already have a position from today (prevent multiple entries on same day)
      if(HasPositionFromToday())
      {
         Print("Position already exists from today. Skipping new entry.");
         g_BreakoutDetected = true; // Mark as detected to prevent further checks
         return;
      }
      
      // Check previous bar for breakout
      double prevHigh = iHigh(g_TradingSymbol, PERIOD_M15, 1);
      double prevLow = iLow(g_TradingSymbol, PERIOD_M15, 1);
      double prevClose = iClose(g_TradingSymbol, PERIOD_M15, 1);
      
      // Check for breakout above range
      if(prevClose > g_OpeningRangeHigh)
      {
         Print("Breakout detected: Candle closed above opening range high");
         Print("  Opening Range High: ", g_OpeningRangeHigh);
         Print("  Breakout Close: ", prevClose);
         
         // Enter long position
         EnterLongPosition();
         g_BreakoutDetected = true;
      }
      // Check for breakout below range
      else if(prevClose < g_OpeningRangeLow)
      {
         Print("Breakout detected: Candle closed below opening range low");
         Print("  Opening Range Low: ", g_OpeningRangeLow);
         Print("  Breakout Close: ", prevClose);
         
         // Enter short position
         EnterShortPosition();
         g_BreakoutDetected = true;
      }
   }
   
   // Manage trailing stop if enabled
   if(UseTrailingStop && g_BreakoutDetected)
   {
      ManageTrailingStop();
   }
}

//+------------------------------------------------------------------+
//| Check if current time is in trading session (NY time)           |
//+------------------------------------------------------------------+
bool IsInTradingSession()
{
   MqlDateTime dt;
   TimeToStruct(TimeCurrent(), dt);
   
   // Convert to NY time (EST/EDT)
   int nyHour = GetNYTimeHour();
   int nyMinute = dt.min;
   
   int sessionStart = SessionStartHour * 60 + SessionStartMinute;
   int sessionEnd = SessionEndHour * 60 + SessionEndMinute;
   int currentTime = nyHour * 60 + nyMinute;
   
   return (currentTime >= sessionStart && currentTime <= sessionEnd);
}

//+------------------------------------------------------------------+
//| Check if it's a trading day (Monday-Friday or news day)         |
//+------------------------------------------------------------------+
bool IsTradingDay()
{
   MqlDateTime dt;
   TimeToStruct(TimeCurrent(), dt);
   
   // Monday = 1, Friday = 5
   if(dt.day_of_week >= 1 && dt.day_of_week <= 5)
      return true;
   
   // Check for high impact news days (NFP, CPI) if enabled
   if(TradeOnNewsDays)
   {
      // This is a simplified check - you may want to add actual news calendar integration
      // For now, we'll trade on all weekdays
      return (dt.day_of_week >= 1 && dt.day_of_week <= 5);
   }
   
   return false;
}

//+------------------------------------------------------------------+
//| Check if candle is the opening range candle (09:30-09:45 NY)    |
//+------------------------------------------------------------------+
bool IsOpeningRangeCandle(datetime candleTime)
{
   MqlDateTime dt;
   TimeToStruct(candleTime, dt);
   
   int nyHour = GetNYTimeHourFromDT(dt);
   int nyMinute = dt.min;
   
   int rangeStart = OpeningRangeStartHour * 60 + OpeningRangeStartMinute;
   int rangeEnd = OpeningRangeStartHour * 60 + OpeningRangeEndMinute;
   int candleTimeMinutes = nyHour * 60 + nyMinute;
   
   return (candleTimeMinutes >= rangeStart && candleTimeMinutes < rangeEnd);
}

//+------------------------------------------------------------------+
//| Get NY time hour from current time                               |
//+------------------------------------------------------------------+
int GetNYTimeHour()
{
   MqlDateTime dt;
   TimeToStruct(TimeCurrent(), dt);
   return GetNYTimeHourFromDT(dt);
}

//+------------------------------------------------------------------+
//| Get NY time hour from MqlDateTime                                |
//+------------------------------------------------------------------+
int GetNYTimeHourFromDT(MqlDateTime &dt)
{
   // Convert server time to NY time (EST = UTC-5, EDT = UTC-4)
   // This is a simplified conversion - adjust based on your broker's timezone
   // Most brokers use GMT+2 or GMT+3 for server time
   // NY time is typically GMT-5 (EST) or GMT-4 (EDT)
   
   // Get server timezone offset (in hours)
   datetime serverTime = StructToTime(dt);
   datetime gmtTime = TimeGMT();
   int serverOffset = (int)((serverTime - gmtTime) / 3600);
   
   // NY time offset (EST = -5, EDT = -4)
   // Simple approximation: assume EST (-5) for winter, EDT (-4) for summer
   int nyOffset = -5; // Default to EST
   if(dt.mon >= 3 && dt.mon <= 10) // Rough DST period
      nyOffset = -4; // EDT
   
   // Calculate NY hour
   int nyHour = dt.hour - serverOffset + nyOffset;
   
   // Handle day rollover
   if(nyHour < 0)
      nyHour += 24;
   else if(nyHour >= 24)
      nyHour -= 24;
   
   return nyHour;
}

//+------------------------------------------------------------------+
//| Enter long position on breakout above range                      |
//+------------------------------------------------------------------+
void EnterLongPosition()
{
   // Get current price
   double ask = SymbolInfoDouble(g_TradingSymbol, SYMBOL_ASK);
   double bid = SymbolInfoDouble(g_TradingSymbol, SYMBOL_BID);
   
   // Entry price (market order)
   double entryPrice = ask;
   
   // Stop loss at opening range low
   double stopLoss = g_OpeningRangeLow;
   
   // Calculate stop loss distance
   double slDistance = entryPrice - stopLoss;
   if(slDistance <= 0)
   {
      Print("ERROR: Invalid stop loss distance for long position");
      return;
   }
   
   // Take profit = SL distance * Risk/Reward ratio
   double takeProfit = entryPrice + (slDistance * RiskRewardRatio);
   
   // Calculate position size based on fixed USD risk
   double lotSize = CalculatePositionSize(slDistance, FixedRiskUSD);
   
   if(lotSize <= 0)
   {
      Print("ERROR: Invalid lot size calculated");
      return;
   }
   
   // Normalize lot size
   double minLot = SymbolInfoDouble(g_TradingSymbol, SYMBOL_VOLUME_MIN);
   double maxLot = SymbolInfoDouble(g_TradingSymbol, SYMBOL_VOLUME_MAX);
   double lotStep = SymbolInfoDouble(g_TradingSymbol, SYMBOL_VOLUME_STEP);
   
   lotSize = MathFloor(lotSize / lotStep) * lotStep;
   lotSize = MathMax(minLot, MathMin(maxLot, lotSize));
   
   // Place market order
   MqlTradeRequest request = {};
   MqlTradeResult result = {};
   
   request.action = TRADE_ACTION_DEAL;
   request.symbol = g_TradingSymbol;
   request.volume = lotSize;
   request.type = ORDER_TYPE_BUY;
   request.price = ask;
   request.sl = stopLoss;
   request.tp = UseTrailingStop ? 0 : takeProfit; // No TP if trailing stop enabled
   request.deviation = 10;
   request.magic = MagicNumber;
   request.comment = "NYSE ORB Long";
   request.type_filling = ORDER_FILLING_FOK;
   
   // Try FOK, if fails try IOC
   if(!OrderSend(request, result))
   {
      request.type_filling = ORDER_FILLING_IOC;
      if(!OrderSend(request, result))
      {
         Print("ERROR: Failed to open long position. Retcode: ", result.retcode, 
               ", Comment: ", result.comment);
         return;
      }
   }
   
   Print("Long position opened:");
   Print("  Entry: ", entryPrice);
   Print("  Stop Loss: ", stopLoss);
   Print("  Take Profit: ", UseTrailingStop ? "Trailing" : DoubleToString(takeProfit, _Digits));
   Print("  Lot Size: ", lotSize);
   Print("  Risk: $", FixedRiskUSD);
}

//+------------------------------------------------------------------+
//| Enter short position on breakout below range                     |
//+------------------------------------------------------------------+
void EnterShortPosition()
{
   // Get current price
   double ask = SymbolInfoDouble(g_TradingSymbol, SYMBOL_ASK);
   double bid = SymbolInfoDouble(g_TradingSymbol, SYMBOL_BID);
   
   // Entry price (market order)
   double entryPrice = bid;
   
   // Stop loss at opening range high
   double stopLoss = g_OpeningRangeHigh;
   
   // Calculate stop loss distance
   double slDistance = stopLoss - entryPrice;
   if(slDistance <= 0)
   {
      Print("ERROR: Invalid stop loss distance for short position");
      return;
   }
   
   // Take profit = SL distance * Risk/Reward ratio
   double takeProfit = entryPrice - (slDistance * RiskRewardRatio);
   
   // Calculate position size based on fixed USD risk
   double lotSize = CalculatePositionSize(slDistance, FixedRiskUSD);
   
   if(lotSize <= 0)
   {
      Print("ERROR: Invalid lot size calculated");
      return;
   }
   
   // Normalize lot size
   double minLot = SymbolInfoDouble(g_TradingSymbol, SYMBOL_VOLUME_MIN);
   double maxLot = SymbolInfoDouble(g_TradingSymbol, SYMBOL_VOLUME_MAX);
   double lotStep = SymbolInfoDouble(g_TradingSymbol, SYMBOL_VOLUME_STEP);
   
   lotSize = MathFloor(lotSize / lotStep) * lotStep;
   lotSize = MathMax(minLot, MathMin(maxLot, lotSize));
   
   // Place market order
   MqlTradeRequest request = {};
   MqlTradeResult result = {};
   
   request.action = TRADE_ACTION_DEAL;
   request.symbol = g_TradingSymbol;
   request.volume = lotSize;
   request.type = ORDER_TYPE_SELL;
   request.price = bid;
   request.sl = stopLoss;
   request.tp = UseTrailingStop ? 0 : takeProfit; // No TP if trailing stop enabled
   request.deviation = 10;
   request.magic = MagicNumber;
   request.comment = "NYSE ORB Short";
   request.type_filling = ORDER_FILLING_FOK;
   
   // Try FOK, if fails try IOC
   if(!OrderSend(request, result))
   {
      request.type_filling = ORDER_FILLING_IOC;
      if(!OrderSend(request, result))
      {
         Print("ERROR: Failed to open short position. Retcode: ", result.retcode, 
               ", Comment: ", result.comment);
         return;
      }
   }
   
   Print("Short position opened:");
   Print("  Entry: ", entryPrice);
   Print("  Stop Loss: ", stopLoss);
   Print("  Take Profit: ", UseTrailingStop ? "Trailing" : DoubleToString(takeProfit, _Digits));
   Print("  Lot Size: ", lotSize);
   Print("  Risk: $", FixedRiskUSD);
}

//+------------------------------------------------------------------+
//| Calculate position size based on fixed USD risk                 |
//+------------------------------------------------------------------+
double CalculatePositionSize(double slDistance, double riskUSD)
{
   if(slDistance <= 0)
      return 0;
   
   // Get tick value and tick size
   double tickValue = SymbolInfoDouble(g_TradingSymbol, SYMBOL_TRADE_TICK_VALUE);
   double tickSize = SymbolInfoDouble(g_TradingSymbol, SYMBOL_TRADE_TICK_SIZE);
   double point = SymbolInfoDouble(g_TradingSymbol, SYMBOL_POINT);
   
   if(tickValue <= 0 || tickSize <= 0 || point <= 0)
      return 0;
   
   // Calculate ticks in stop loss distance
   double ticksInSL = slDistance / tickSize;
   
   // Calculate lot size: riskUSD / (ticksInSL * tickValue)
   double lotSize = riskUSD / (ticksInSL * tickValue);
   
   return lotSize;
}

//+------------------------------------------------------------------+
//| Manage trailing stop loss                                        |
//+------------------------------------------------------------------+
void ManageTrailingStop()
{
   // Find open positions with our magic number
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      ulong ticket = PositionGetTicket(i);
      if(ticket <= 0)
         continue;
      
      if(PositionGetString(POSITION_SYMBOL) != g_TradingSymbol)
         continue;
      
      if(PositionGetInteger(POSITION_MAGIC) != MagicNumber)
         continue;
      
      // Get position details
      double positionOpenPrice = PositionGetDouble(POSITION_PRICE_OPEN);
      double currentSL = PositionGetDouble(POSITION_SL);
      long positionType = PositionGetInteger(POSITION_TYPE);
      
      // Get current price
      double currentPrice = (positionType == POSITION_TYPE_BUY) ? 
                           SymbolInfoDouble(g_TradingSymbol, SYMBOL_BID) : 
                           SymbolInfoDouble(g_TradingSymbol, SYMBOL_ASK);
      
      // Calculate initial risk (R) - distance from entry to original SL
      double initialRisk = 0;
      if(positionType == POSITION_TYPE_BUY)
         initialRisk = positionOpenPrice - g_OpeningRangeLow;
      else
         initialRisk = g_OpeningRangeHigh - positionOpenPrice;
      
      if(initialRisk <= 0)
         continue;
      
      // Calculate current profit in R
      double currentProfitR = 0;
      if(positionType == POSITION_TYPE_BUY)
         currentProfitR = (currentPrice - positionOpenPrice) / initialRisk;
      else
         currentProfitR = (positionOpenPrice - currentPrice) / initialRisk;
      
      // Start trailing when position is 1R in profit
      if(currentProfitR < 1.0)
         continue;
      
      // Calculate trailing distance (0.15R)
      double trailingDistance = initialRisk * TrailingStopRatio;
      
      // Reference point for trailing: use current SL if exists, otherwise entry price
      double referencePrice = (currentSL > 0) ? currentSL : positionOpenPrice;
      
      if(positionType == POSITION_TYPE_BUY)
      {
         // Calculate how far price has moved from reference point
         double priceMoveFromReference = currentPrice - referencePrice;
         double priceMoveR = priceMoveFromReference / initialRisk;
         
         // If price moved 0.15R in favor, trail SL by 0.15R
         if(priceMoveR >= TrailingStopRatio)
         {
            // New SL should be 0.15R from current price
            double newSL = currentPrice - trailingDistance;
            
            // Only move SL up, never down
            if(newSL > currentSL && newSL < currentPrice)
            {
               ModifyStopLoss(ticket, newSL);
            }
         }
      }
      else // SHORT
      {
         // Calculate how far price has moved from reference point
         double priceMoveFromReference = referencePrice - currentPrice;
         double priceMoveR = priceMoveFromReference / initialRisk;
         
         // If price moved 0.15R in favor, trail SL by 0.15R
         if(priceMoveR >= TrailingStopRatio)
         {
            // New SL should be 0.15R from current price
            double newSL = currentPrice + trailingDistance;
            
            // Only move SL down, never up
            if((currentSL == 0 || newSL < currentSL) && newSL > currentPrice)
            {
               ModifyStopLoss(ticket, newSL);
            }
         }
      }
   }
}

//+------------------------------------------------------------------+
//| Check if we have a position opened today                         |
//+------------------------------------------------------------------+
bool HasPositionFromToday()
{
   MqlDateTime currentDT;
   TimeToStruct(TimeCurrent(), currentDT);
   int currentDay = currentDT.day;
   int currentMonth = currentDT.mon;
   int currentYear = currentDT.year;
   
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      ulong ticket = PositionGetTicket(i);
      if(ticket <= 0)
         continue;
      
      if(PositionGetString(POSITION_SYMBOL) != g_TradingSymbol)
         continue;
      
      if(PositionGetInteger(POSITION_MAGIC) != MagicNumber)
         continue;
      
      // Get position open time
      datetime positionOpenTime = (datetime)PositionGetInteger(POSITION_TIME);
      MqlDateTime posDT;
      TimeToStruct(positionOpenTime, posDT);
      
      // Check if position was opened today
      if(posDT.day == currentDay && posDT.mon == currentMonth && posDT.year == currentYear)
         return true;
   }
   
   return false;
}

//+------------------------------------------------------------------+
//| Modify stop loss of a position                                   |
//+------------------------------------------------------------------+
void ModifyStopLoss(ulong ticket, double newSL)
{
   MqlTradeRequest request = {};
   MqlTradeResult result = {};
   
   if(!PositionSelectByTicket(ticket))
   {
      Print("ERROR: Position not found for ticket ", ticket);
      return;
   }
   
   double currentTP = PositionGetDouble(POSITION_TP);
   
   request.action = TRADE_ACTION_SLTP;
   request.position = ticket;
   request.symbol = g_TradingSymbol;
   request.sl = newSL;
   request.tp = currentTP;
   
   if(!OrderSend(request, result))
   {
      Print("ERROR: Failed to modify stop loss. Retcode: ", result.retcode, 
            ", Comment: ", result.comment);
      return;
   }
   
   Print("Stop loss modified for ticket ", ticket, " to ", newSL);
}

//+------------------------------------------------------------------+

