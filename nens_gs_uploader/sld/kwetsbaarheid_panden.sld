<?xml version="1.0" encoding="UTF-8"?>
<StyledLayerDescriptor xmlns="http://www.opengis.net/sld" xmlns:ogc="http://www.opengis.net/ogc" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" version="1.1.0" xmlns:xlink="http://www.w3.org/1999/xlink" xsi:schemaLocation="http://www.opengis.net/sld http://schemas.opengis.net/sld/1.1.0/StyledLayerDescriptor.xsd" xmlns:se="http://www.opengis.net/se">
  <NamedLayer>
    <se:Name>panden_zh</se:Name>
    <UserStyle>
      <se:Name>panden_zh</se:Name>
      <se:FeatureTypeStyle>
        <se:Rule>
          <se:Name> &lt; 0.10</se:Name>
          <se:Description>
            <se:Title> &lt; 0.10</se:Title>
			</se:Description>
			<ogc:Filter xmlns:ogc="http://www.opengis.net/ogc">
				<ogc:And>
				<ogc:PropertyIsGreaterThanOrEqualTo>
					<ogc:PropertyName>wp_waterhoogte_tov_vloerpeil</ogc:PropertyName>
					<ogc:Literal>0.02</ogc:Literal>
				</ogc:PropertyIsGreaterThanOrEqualTo>
				<ogc:PropertyIsLessThanOrEqualTo>
					<ogc:PropertyName>wp_waterhoogte_tov_vloerpeil</ogc:PropertyName>
					<ogc:Literal>0.1</ogc:Literal>
				</ogc:PropertyIsLessThanOrEqualTo>
				</ogc:And>
			</ogc:Filter>
			<se:PolygonSymbolizer>
            <se:Fill>
              <se:SvgParameter name="fill">#fedbb7</se:SvgParameter>
            </se:Fill>
          </se:PolygonSymbolizer>
        </se:Rule>
        <se:Rule>
          <se:Name> 0.10 - 0.25 </se:Name>
          <se:Description>
            <se:Title> 0.10 - 0.25 </se:Title>
          </se:Description>
          <ogc:Filter xmlns:ogc="http://www.opengis.net/ogc">
            <ogc:And>
              <ogc:PropertyIsGreaterThan>
                <ogc:PropertyName>wp_waterhoogte_tov_vloerpeil</ogc:PropertyName>
                <ogc:Literal>0.10</ogc:Literal>
              </ogc:PropertyIsGreaterThan>
              <ogc:PropertyIsLessThanOrEqualTo>
                <ogc:PropertyName>wp_waterhoogte_tov_vloerpeil</ogc:PropertyName>
                <ogc:Literal>0.25</ogc:Literal>
              </ogc:PropertyIsLessThanOrEqualTo>
            </ogc:And>
          </ogc:Filter>
          <se:PolygonSymbolizer>
            <se:Fill>
              <se:SvgParameter name="fill">#f67722</se:SvgParameter>
            </se:Fill>
          </se:PolygonSymbolizer>
        </se:Rule>
        <se:Rule>
          <se:Name>> 0.25</se:Name>
          <se:Description>
            <se:Title>> 0.25</se:Title>
          </se:Description>
          <ogc:Filter xmlns:ogc="http://www.opengis.net/ogc">
            <ogc:And>
              <ogc:PropertyIsGreaterThan>
                <ogc:PropertyName>wp_waterhoogte_tov_vloerpeil</ogc:PropertyName>
                <ogc:Literal>0.25</ogc:Literal>
              </ogc:PropertyIsGreaterThan>
              <ogc:PropertyIsLessThanOrEqualTo>
                <ogc:PropertyName>wp_waterhoogte_tov_vloerpeil</ogc:PropertyName>
                <ogc:Literal>9999</ogc:Literal>
              </ogc:PropertyIsLessThanOrEqualTo>
            </ogc:And>
          </ogc:Filter>
          <se:PolygonSymbolizer>
            <se:Fill>
              <se:SvgParameter name="fill">#7f2704</se:SvgParameter>
            </se:Fill>
          </se:PolygonSymbolizer>
        </se:Rule>
      </se:FeatureTypeStyle>
    </UserStyle>
  </NamedLayer>
</StyledLayerDescriptor>
