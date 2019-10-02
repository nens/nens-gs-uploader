<?xml version="1.0" encoding="UTF-8"?>
<StyledLayerDescriptor xmlns="http://www.opengis.net/sld" xmlns:ogc="http://www.opengis.net/ogc" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" version="1.1.0" xmlns:xlink="http://www.w3.org/1999/xlink" xsi:schemaLocation="http://www.opengis.net/sld http://schemas.opengis.net/sld/1.1.0/StyledLayerDescriptor.xsd" xmlns:se="http://www.opengis.net/se">
  <NamedLayer>
    <se:Name>1825_regenwaterstructuurkaart</se:Name>
    <UserStyle>
      <se:Name>1825_regenwaterstructuurkaart</se:Name>
      <se:FeatureTypeStyle>
        <se:Rule>
          <se:Name>1e orde</se:Name>
          <se:Description>
            <se:Title>1e orde</se:Title>
          </se:Description>
          <ogc:Filter xmlns:ogc="http://www.opengis.net/ogc">
            <ogc:PropertyIsEqualTo>
              <ogc:PropertyName>orde</ogc:PropertyName>
              <ogc:Literal>1</ogc:Literal>
            </ogc:PropertyIsEqualTo>
          </ogc:Filter>
          <se:LineSymbolizer>
            <se:Stroke>
              <se:SvgParameter name="stroke">#1ba1f3</se:SvgParameter>
              <se:SvgParameter name="stroke-width">4</se:SvgParameter>
              <se:SvgParameter name="stroke-linejoin">bevel</se:SvgParameter>
              <se:SvgParameter name="stroke-linecap">round</se:SvgParameter>
            </se:Stroke>
          </se:LineSymbolizer>
          <se:PointSymbolizer>
            <se:Geometry>
              <ogc:Function name="endPoint">
               <ogc:PropertyName>geom</ogc:PropertyName>
              </ogc:Function>
            </se:Geometry>
             <se:Graphic>
               <se:Mark>
                 <se:WellKnownName>filled_arrowhead</se:WellKnownName>
                 <se:Fill>
                   <se:SvgParameter name="fill">#2e2bd9</se:SvgParameter>
                 </se:Fill>
                 <se:Stroke>
                   <se:SvgParameter name="stroke">#4b8fe7</se:SvgParameter>
                   <se:SvgParameter name="stroke-width">1</se:SvgParameter>
                 </se:Stroke>
                </se:Mark>
                <se:Size>22</se:Size>
               <se:Rotation>
                 <ogc:Function name="endAngle">
                 	<ogc:PropertyName>geom</ogc:PropertyName>
                 </ogc:Function>
               </se:Rotation>
             </se:Graphic>
          </se:PointSymbolizer>
        </se:Rule>
        <se:Rule>
          <se:Name>2e orde</se:Name>
          <se:Description>
            <se:Title>2e orde</se:Title>
          </se:Description>
          <ogc:Filter xmlns:ogc="http://www.opengis.net/ogc">
            <ogc:PropertyIsEqualTo>
              <ogc:PropertyName>orde</ogc:PropertyName>
              <ogc:Literal>2</ogc:Literal>
            </ogc:PropertyIsEqualTo>
          </ogc:Filter>
          <se:MaxScaleDenominator>36000</se:MaxScaleDenominator>
          <se:LineSymbolizer>
            <se:Stroke>
              <se:SvgParameter name="stroke">#171399</se:SvgParameter>
              <se:SvgParameter name="stroke-width">2</se:SvgParameter>
              <se:SvgParameter name="stroke-linejoin">bevel</se:SvgParameter>
              <se:SvgParameter name="stroke-linecap">square</se:SvgParameter>
            </se:Stroke>
          </se:LineSymbolizer>
          <se:PointSymbolizer>
            <se:Geometry>
              <ogc:Function name="endPoint">
               <ogc:PropertyName>geom</ogc:PropertyName>
              </ogc:Function>
            </se:Geometry>
             <se:Graphic>
               <se:Mark>
                 <se:WellKnownName>filled_arrowhead</se:WellKnownName>
                 <se:Fill>
                   <se:SvgParameter name="fill">#171399</se:SvgParameter>
                 </se:Fill>
                 <se:Stroke>
                   <se:SvgParameter name="stroke">#171399</se:SvgParameter>
                   <se:SvgParameter name="stroke-width">1</se:SvgParameter>
                 </se:Stroke>
                </se:Mark>
                <se:Size>14</se:Size>
               <se:Rotation>
                 <ogc:Function name="endAngle">
                 	<ogc:PropertyName>geom</ogc:PropertyName>
                 </ogc:Function>
               </se:Rotation>
             </se:Graphic>
          </se:PointSymbolizer>
        </se:Rule>
        <se:Rule>
          <se:Name>0e orde</se:Name>
          <se:Description>
            <se:Title>0e orde</se:Title>
          </se:Description>
          <ogc:Filter xmlns:ogc="http://www.opengis.net/ogc">
            <ogc:PropertyIsEqualTo>
              <ogc:PropertyName>orde</ogc:PropertyName>
              <ogc:Literal>0</ogc:Literal>
            </ogc:PropertyIsEqualTo>
          </ogc:Filter>
          <se:LineSymbolizer>
            <se:Stroke>
              <se:SvgParameter name="stroke">#1ba1f3</se:SvgParameter>
              <se:SvgParameter name="stroke-width">4</se:SvgParameter>
              <se:SvgParameter name="stroke-linejoin">bevel</se:SvgParameter>
              <se:SvgParameter name="stroke-linecap">butt</se:SvgParameter>
              <se:SvgParameter name="stroke-dasharray">4 2</se:SvgParameter>
            </se:Stroke>
          </se:LineSymbolizer>
        </se:Rule>
      </se:FeatureTypeStyle>
    </UserStyle>
  </NamedLayer>
</StyledLayerDescriptor>
